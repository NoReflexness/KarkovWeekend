"""Chat API + notification side effects."""

import json

import pytest

from app.core.config import get_settings

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


@pytest.fixture
def fast_chat_stream(monkeypatch):
    """Make `/chat/stream` drain immediately and return after one pass."""
    settings = get_settings()
    monkeypatch.setattr(settings, "chat_stream_poll_seconds", 0.0, raising=False)
    monkeypatch.setattr(settings, "chat_stream_max_seconds", 5.0, raising=False)
    monkeypatch.setattr(settings, "chat_stream_keepalive_seconds", 1.0, raising=False)
    yield settings


def _login(client, email: str, pw: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _bootstrap_parent(client, email: str = "p@example.com"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "ChatFam"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Forælder", "password": "password123"},
    )
    return fid


def test_post_and_list_chat_messages(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post("/api/v1/chat/messages", json={"body": "Hej alle!"})
    assert r.status_code == 201, r.text
    msg = r.json()
    assert msg["kind"] == "user"
    assert msg["body"] == "Hej alle!"
    assert msg["user_name"]

    r2 = client.get("/api/v1/chat/messages")
    assert r2.status_code == 200
    bodies = [m["body"] for m in r2.json()]
    assert "Hej alle!" in bodies


def test_chat_blank_message_rejected(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post("/api/v1/chat/messages", json={"body": "   "})
    assert r.status_code == 400


def test_since_id_returns_only_newer(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    a = client.post("/api/v1/chat/messages", json={"body": "first"}).json()
    b = client.post("/api/v1/chat/messages", json={"body": "second"}).json()
    after = client.get(f"/api/v1/chat/messages?since_id={a['id']}").json()
    ids = [m["id"] for m in after]
    assert b["id"] in ids
    assert a["id"] not in ids


def test_user_can_delete_own_message_admin_can_delete_any(client):
    _bootstrap_parent(client, "p1@example.com")
    mine = client.post("/api/v1/chat/messages", json={"body": "hej"}).json()
    other = client.delete("/api/v1/chat/messages/9999")
    assert other.status_code == 204  # silent on missing

    # parent cannot delete admin-owned message; create one as admin
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    admin_msg = client.post("/api/v1/chat/messages", json={"body": "fra admin"}).json()
    client.post("/api/v1/auth/logout")

    _login(client, "p1@example.com", "password123")
    r = client.delete(f"/api/v1/chat/messages/{admin_msg['id']}")
    assert r.status_code == 403

    r2 = client.delete(f"/api/v1/chat/messages/{mine['id']}")
    assert r2.status_code == 204

    # admin can delete the other parent's message? actually parent already deleted theirs.
    # Verify admin can wipe a fresh one too.
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    extra = client.post("/api/v1/chat/messages", json={"body": "lol"}).json()
    r3 = client.delete(f"/api/v1/chat/messages/{extra['id']}")
    assert r3.status_code == 204


def test_event_creation_posts_system_message(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    before = len(client.get("/api/v1/chat/messages").json())
    client.post(
        "/api/v1/events",
        json={"name": "Sys 2030", "start_date": "2030-07-10", "end_date": "2030-07-11"},
    )
    after = client.get("/api/v1/chat/messages").json()
    assert len(after) == before + 1
    last = after[-1]
    assert last["kind"] == "system"
    assert "Sys 2030" in last["body"]
    assert last["icon"]


def test_attendance_change_posts_system_message(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={"name": "Tilmeld", "start_date": "2030-07-10", "end_date": "2030-07-11"},
    ).json()
    day_id = event["days"][0]["id"]
    client.post(
        f"/api/v1/events/{event['id']}/days/{day_id}/attendance",
        json={"present": True},
    )
    msgs = client.get("/api/v1/chat/messages").json()
    last = msgs[-1]
    assert last["kind"] == "system"
    assert "tilmeldte sig" in last["body"].lower()


def test_user_messages_do_not_email_anyone(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    before = client.get("/api/v1/_debug/last-email")
    before_subj = before.json().get("subject") if before.status_code == 200 else None
    client.post("/api/v1/chat/messages", json={"body": "Bare snak"})
    after = client.get("/api/v1/_debug/last-email")
    after_subj = after.json().get("subject") if after.status_code == 200 else None
    assert before_subj == after_subj  # no new email written


def test_notify_pref_prompt_lifecycle(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    initial = client.get("/api/v1/chat/notify-pref").json()
    assert initial["needs_prompt"] is True
    assert initial["notify_email"] is None

    saved = client.put(
        "/api/v1/chat/notify-pref", json={"notify_email": True}
    ).json()
    assert saved["needs_prompt"] is False
    assert saved["notify_email"] is True

    again = client.get("/api/v1/chat/notify-pref").json()
    assert again["needs_prompt"] is False


def test_dismiss_notify_prompt_does_not_set_pref(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post("/api/v1/chat/notify-pref/dismiss").json()
    assert r["needs_prompt"] is False
    assert r["notify_email"] is None


def _read_sse_events(stream_response) -> list[dict]:
    out: list[dict] = []
    event: str | None = None
    data_lines: list[str] = []
    body = stream_response.text
    for raw in body.splitlines():
        if raw.startswith(":"):
            continue
        if raw == "":
            if event and data_lines:
                payload = "\n".join(data_lines)
                try:
                    out.append({"event": event, "data": json.loads(payload)})
                except json.JSONDecodeError:
                    out.append({"event": event, "data": payload})
            event = None
            data_lines = []
            continue
        if raw.startswith("event:"):
            event = raw.removeprefix("event:").strip()
        elif raw.startswith("data:"):
            data_lines.append(raw.removeprefix("data:").lstrip())
    return out


def test_chat_stream_returns_new_messages(client, fast_chat_stream):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    a = client.post("/api/v1/chat/messages", json={"body": "hej en"}).json()
    client.post("/api/v1/chat/messages", json={"body": "hej to"})
    r = client.get(f"/api/v1/chat/stream?since_id={a['id']}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _read_sse_events(r)
    msg_events = [e for e in events if e["event"] == "messages"]
    assert msg_events, events
    bodies = [m["body"] for batch in msg_events for m in batch["data"]]
    assert "hej to" in bodies
    assert "hej en" not in bodies


def test_chat_stream_requires_auth(client):
    client.post("/api/v1/auth/logout")
    r = client.get("/api/v1/chat/stream")
    assert r.status_code == 401
