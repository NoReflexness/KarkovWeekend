"""Coalescing of attendance/activity/chor notifications into one summary."""

from app.core.config import get_settings
from app.models.pending_notification import PendingNotification

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _bootstrap_parent(client, email="parent@example.com", name="Parent"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": name, "password": "password123"},
    )
    return fid


def _set_debounce(seconds: int) -> None:
    """Override the global debounce window for the duration of a test."""
    get_settings.cache_clear()
    s = get_settings()
    s.notification_debounce_seconds = seconds  # type: ignore[misc]


def test_attendance_multi_day_coalesces_into_single_message(client, db_session):
    _set_debounce(60)
    try:
        _bootstrap_parent(client, email="multi@example.com", name="Multi")
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        event = client.post(
            "/api/v1/events",
            json={"name": "Coalesce", "start_date": "2030-07-10", "end_date": "2030-07-13"},
        ).json()
        client.post(f"/api/v1/events/{event['id']}/open")
        client.post("/api/v1/auth/logout")

        _login(client, "multi@example.com", "password123")
        before = client.get("/api/v1/chat/messages").json()
        n_before = len(before)

        for d in event["days"]:
            r = client.post(
                f"/api/v1/events/{event['id']}/days/{d['id']}/attendance",
                json={"present": True},
            )
            assert r.status_code == 200, r.text

        # Within the debounce window -> nothing posted yet.
        mid = client.get("/api/v1/chat/messages").json()
        assert len(mid) == n_before, "system message must not appear before flush"

        pending = db_session.query(PendingNotification).all()
        assert len(pending) == 1
        assert pending[0].data["days_added"] == 4

        # Force flush and verify a single coalesced summary.
        from app.services.notification_queue import flush_all_pending_notifications

        flush_all_pending_notifications(db_session)
        db_session.commit()

        after = client.get("/api/v1/chat/messages").json()
        new = after[len(before):]
        sys_msgs = [m for m in new if m["kind"] == "system"]
        assert len(sys_msgs) == 1, sys_msgs
        body = sys_msgs[0]["body"]
        assert "4 dage" in body
        assert "Coalesce" in body
    finally:
        _set_debounce(0)


def test_activity_multi_join_coalesces(client, db_session):
    _set_debounce(60)
    try:
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        event = client.post(
            "/api/v1/events",
            json={"name": "ActSpam", "start_date": "2030-07-10", "end_date": "2030-07-11"},
        ).json()
        day_id = event["days"][0]["id"]
        a1 = client.post(
            f"/api/v1/events/{event['id']}/days/{day_id}/activities",
            json={"name": "Tur", "time": "10:00"},
        ).json()
        a2 = client.post(
            f"/api/v1/events/{event['id']}/days/{day_id}/activities",
            json={"name": "Spil", "time": "14:00"},
        ).json()
        me = client.get("/api/v1/auth/me").json()

        before = client.get("/api/v1/chat/messages").json()

        client.post(
            f"/api/v1/activities/{a1['id']}/attendees", json={"user_ids": [me["id"]]}
        )
        client.post(
            f"/api/v1/activities/{a2['id']}/attendees", json={"user_ids": [me["id"]]}
        )

        mid = client.get("/api/v1/chat/messages").json()
        # Activity-create messages aren't queued; only joins are.
        join_sys_before_flush = [
            m
            for m in mid[len(before):]
            if m["kind"] == "system" and "tilmeldte" in m["body"].lower()
        ]
        assert join_sys_before_flush == []

        from app.services.notification_queue import flush_all_pending_notifications

        flush_all_pending_notifications(db_session)
        db_session.commit()

        after = client.get("/api/v1/chat/messages").json()
        join_sys = [
            m
            for m in after
            if m["kind"] == "system" and "tilmeldte" in m["body"].lower()
        ]
        assert len(join_sys) == 1, [m["body"] for m in join_sys]
        body = join_sys[0]["body"]
        assert "Tur" in body and "Spil" in body
    finally:
        _set_debounce(0)


def test_chor_multi_assign_coalesces(client, db_session):
    _set_debounce(60)
    try:
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        event = client.post(
            "/api/v1/events",
            json={"name": "ChorSpam", "start_date": "2030-07-10", "end_date": "2030-07-11"},
        ).json()
        day_id = event["days"][0]["id"]
        chors = client.get(
            f"/api/v1/events/{event['id']}/unassigned-chors"
        ).json()
        assert len(chors) >= 3
        me = client.get("/api/v1/auth/me").json()

        before = client.get("/api/v1/chat/messages").json()
        for c in chors[:3]:
            client.post(
                f"/api/v1/chors/{c['id']}/assign", json={"user_id": me["id"]}
            )

        mid = client.get("/api/v1/chat/messages").json()
        chor_sys_before = [
            m for m in mid[len(before):] if m["kind"] == "system" and "opgave" in m["body"]
        ]
        assert chor_sys_before == []

        from app.services.notification_queue import flush_all_pending_notifications

        flush_all_pending_notifications(db_session)
        db_session.commit()

        after = client.get("/api/v1/chat/messages").json()
        chor_sys = [
            m for m in after if m["kind"] == "system" and "opgave" in m["body"]
        ]
        assert len(chor_sys) == 1, [m["body"] for m in chor_sys]
        body = chor_sys[0]["body"]
        for c in chors[:3]:
            assert c["meal"] in body
            assert c["action"] in body
    finally:
        _set_debounce(0)


def test_chat_list_flushes_due_notifications(client, db_session):
    """Reading the chat flushes any rows whose deadline has passed."""
    from datetime import timedelta

    from app.core.security import now_utc
    from app.models.pending_notification import PendingNotificationKind

    _set_debounce(60)
    try:
        _bootstrap_parent(client, email="reader@example.com", name="Reader")
        _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
        event = client.post(
            "/api/v1/events",
            json={"name": "Reader", "start_date": "2030-07-10", "end_date": "2030-07-11"},
        ).json()
        client.post(f"/api/v1/events/{event['id']}/open")
        client.post("/api/v1/auth/logout")
        _login(client, "reader@example.com", "password123")

        day_id = event["days"][0]["id"]
        client.post(
            f"/api/v1/events/{event['id']}/days/{day_id}/attendance",
            json={"present": True},
        )

        # Manually backdate the pending row so it should be flushed on next read.
        row = (
            db_session.query(PendingNotification)
            .filter(PendingNotification.kind == PendingNotificationKind.ATTENDANCE)
            .one()
        )
        row.flush_at = now_utc() - timedelta(seconds=1)
        db_session.commit()

        after = client.get("/api/v1/chat/messages").json()
        sys_msgs = [
            m for m in after if m["kind"] == "system" and "tilmeldte" in m["body"].lower()
        ]
        assert sys_msgs, "expected attendance summary to be flushed on chat read"

        remaining = db_session.query(PendingNotification).all()
        assert remaining == []
    finally:
        _set_debounce(0)
