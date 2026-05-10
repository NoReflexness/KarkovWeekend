"""Finalize flow tests: lock expenses, send notification emails."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _bootstrap(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "p@example.com"}
    ).json()["token"]
    e = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()
    client.post(f"/api/v1/events/{e['id']}/open")
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "P", "password": "passpass1"},
    )
    for d in e["days"]:
        client.post(
            f"/api/v1/events/{e['id']}/days/{d['id']}/attendance",
            json={"present": True},
        )
    return e


def test_finalize_admin_locks_and_emails(client):
    event = _bootstrap(client)
    # add an expense
    cats = {c["name"]: c["id"] for c in client.get("/api/v1/expense-categories").json()}
    client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 1000},
    )

    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(f"/api/v1/events/{event['id']}/finalize")
    assert r.status_code == 200
    assert r.json()["status"] == "afsluttet"

    # admin can still adjust on a locked event
    admin_add = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 50, "description": "Late"},
    )
    assert admin_add.status_code == 201, admin_add.text

    # but non-admins cannot
    client.post("/api/v1/auth/logout")
    _login(client, "p@example.com", "passpass1")
    add = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 100},
    )
    assert add.status_code == 400

    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    box = client.get("/api/v1/_debug/outbox").json()
    assert any("Endeligt regnskab" in r["subject"] for r in box)


def test_finalize_blocked_for_non_admin_non_host(client):
    event = _bootstrap(client)
    r = client.post(f"/api/v1/events/{event['id']}/finalize")
    assert r.status_code == 403


def test_finalize_idempotent(client):
    event = _bootstrap(client)
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r1 = client.post(f"/api/v1/events/{event['id']}/finalize")
    r2 = client.post(f"/api/v1/events/{event['id']}/finalize")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["status"] == "afsluttet"


def test_host_can_finalize(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "host@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Host", "password": "passpass1"},
    )
    me = client.get("/api/v1/auth/me").json()

    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e = client.post(
        "/api/v1/events",
        json={
            "name": "E",
            "start_date": "2026-07-10",
            "end_date": "2026-07-11",
            "host_user_id": me["id"],
        },
    ).json()
    client.post(f"/api/v1/events/{e['id']}/open")
    client.post("/api/v1/auth/logout")
    _login(client, "host@example.com", "passpass1")
    r = client.post(f"/api/v1/events/{e['id']}/finalize")
    assert r.status_code == 200
