"""Web Push subscription endpoints + fan-out wiring."""

import pytest

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _bootstrap_parent(client, email="parent@example.com", password="password123"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "PushFam"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Forælder", "password": password},
    )


@pytest.fixture
def stub_push(monkeypatch):
    """Replace `fan_out` so tests never hit the actual web-push library."""
    sent: list[dict] = []

    def _fake_fan_out(db, *, user_ids, title, body, url=None, icon=None):
        sent.append(
            {
                "user_ids": list(user_ids),
                "title": title,
                "body": body,
                "url": url,
                "icon": icon,
            }
        )
        return len(user_ids)

    import app.services.notification_queue as nq
    import app.services.notifications as notif

    monkeypatch.setattr(nq, "_push_opted_in", _wrap(_fake_fan_out, "_push_opted_in"))
    monkeypatch.setattr(notif, "_push_opted_in", _wrap(_fake_fan_out, "_push_opted_in"))
    return sent


def _wrap(fan_out, name):
    """Adapt the simple fan_out stub to the `_push_opted_in` signature."""

    def _wrapped(db, *, title, body, url, icon, exclude_user_id):
        from app.models.user import User, UserRole

        q = (
            db.query(User.id)
            .filter(User.notify_email.is_(True))
            .filter(User.role != UserRole.CHILD)
        )
        if exclude_user_id is not None:
            q = q.filter(User.id != exclude_user_id)
        ids = [r[0] for r in q.all()]
        if ids:
            fan_out(db, user_ids=ids, title=title, body=body, url=url, icon=icon)

    _wrapped.__name__ = name
    return _wrapped


def test_vapid_public_key_returns_string(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.get("/api/v1/push/vapid-public-key")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["public_key"], str) and len(body["public_key"]) > 20
    assert body["subject"].startswith("mailto:")


def test_subscriptions_endpoint_requires_auth(client):
    r = client.get("/api/v1/push/subscriptions")
    assert r.status_code == 401


def test_create_list_and_unsubscribe(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    payload = {
        "endpoint": "https://push.example/endpoint/abc",
        "keys": {"p256dh": "p256dh-key-data", "auth": "auth-key-data"},
        "user_agent": "ScratchPad/1.0",
    }
    create = client.post("/api/v1/push/subscriptions", json=payload)
    assert create.status_code == 201, create.text
    out = create.json()
    assert out["endpoint"] == payload["endpoint"]
    assert out["user_agent"] == "ScratchPad/1.0"

    listing = client.get("/api/v1/push/subscriptions").json()
    assert any(s["endpoint"] == payload["endpoint"] for s in listing)

    # idempotent re-create with same endpoint just refreshes keys
    payload2 = {**payload, "keys": {"p256dh": "new-p256dh", "auth": "new-auth"}}
    again = client.post("/api/v1/push/subscriptions", json=payload2)
    assert again.status_code == 201

    # cleanup
    rm = client.post(
        "/api/v1/push/unsubscribe", json={"endpoint": payload["endpoint"]}
    )
    assert rm.status_code == 204
    after = client.get("/api/v1/push/subscriptions").json()
    assert all(s["endpoint"] != payload["endpoint"] for s in after)


def test_subscriptions_are_per_user(client):
    _bootstrap_parent(client, email="alice@example.com")
    client.post(
        "/api/v1/push/subscriptions",
        json={
            "endpoint": "https://push.example/alice",
            "keys": {"p256dh": "x", "auth": "y"},
        },
    )
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    listing = client.get("/api/v1/push/subscriptions").json()
    assert all(s["endpoint"] != "https://push.example/alice" for s in listing)


def test_event_creation_fans_out_push(client, stub_push):
    # Create an opted-in parent who should receive the push.
    _bootstrap_parent(client, email="opted-in@example.com")
    client.put("/api/v1/chat/notify-pref", json={"notify_email": True})
    client.post("/api/v1/auth/logout")

    # Admin creates the event; parent should be the recipient.
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/api/v1/events",
        json={
            "name": "Push Event",
            "start_date": "2030-07-10",
            "end_date": "2030-07-11",
        },
    )

    assert stub_push, "expected at least one push fan-out"
    last = stub_push[-1]
    assert "Push Event" in last["body"]
    assert last["title"] == "Karkov"
    assert last["url"].startswith("/arrangementer/")
