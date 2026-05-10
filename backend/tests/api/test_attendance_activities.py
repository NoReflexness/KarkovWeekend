"""Attendance, activities, and chor assignment tests."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _make_event(client) -> dict:
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-12", "bed_count": 10},
    ).json()
    client.post(f"/api/v1/events/{e['id']}/open")
    return client.get(f"/api/v1/events/{e['id']}").json()


def _make_parent_with_kids(client, email="p@example.com"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Forælder", "password": "password123"},
    )
    kid_a = client.post(
        "/api/v1/me/children", json={"name": "Liva", "birthdate": "2018-04-01"}
    ).json()
    kid_b = client.post(
        "/api/v1/me/children", json={"name": "Baby", "birthdate": "2025-01-01"}
    ).json()
    me = client.get("/api/v1/auth/me").json()
    return me, [kid_a, kid_b]


def test_join_event_auto_includes_kids(client):
    event = _make_event(client)
    client.post("/api/v1/auth/logout")
    me, kids = _make_parent_with_kids(client)

    day = event["days"][0]
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    expected_ids = {me["id"], *(k["id"] for k in kids)}
    assert set(body["attendee_user_ids"]) == expected_ids


def test_leave_event_removes_self_and_kids(client):
    event = _make_event(client)
    client.post("/api/v1/auth/logout")
    me, kids = _make_parent_with_kids(client)
    day = event["days"][0]
    client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True},
    )

    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": False},
    )
    assert r.status_code == 200
    assert me["id"] not in r.json()["attendee_user_ids"]
    for kid in kids:
        assert kid["id"] not in r.json()["attendee_user_ids"]


def test_bulk_set_attendance_for_multiple_days(client):
    event = _make_event(client)
    client.post("/api/v1/auth/logout")
    me, _ = _make_parent_with_kids(client)
    day_ids = [d["id"] for d in event["days"]]
    r = client.post(
        f"/api/v1/events/{event['id']}/attendance",
        json={"day_ids": day_ids[:2], "present": True},
    )
    assert r.status_code == 200
    refreshed = client.get(f"/api/v1/events/{event['id']}").json()
    present = {d["id"]: d["attendee_user_ids"] for d in refreshed["days"]}
    assert me["id"] in present[day_ids[0]]
    assert me["id"] in present[day_ids[1]]
    assert me["id"] not in present[day_ids[2]]


def test_attendance_locked_when_status_locked(client):
    event = _make_event(client)
    client.post(f"/api/v1/events/{event['id']}/lock-attendance")
    client.post("/api/v1/auth/logout")
    _make_parent_with_kids(client)
    day = event["days"][0]
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True},
    )
    assert r.status_code == 400


def test_assign_and_unassign_chor(client):
    event = _make_event(client)
    chor_id = event["days"][0]["chors"][0]["id"]
    client.post("/api/v1/auth/logout")
    me, _ = _make_parent_with_kids(client)

    r = client.post(f"/api/v1/chors/{chor_id}/assign", json={"user_id": me["id"]})
    assert r.status_code == 200
    assert r.json()["assignee_user_id"] == me["id"]

    # other parent cannot reassign
    client.post("/api/v1/auth/logout")
    me2, _ = _make_parent_with_kids(client, email="p2@example.com")
    r = client.post(f"/api/v1/chors/{chor_id}/assign", json={"user_id": me2["id"]})
    assert r.status_code == 400  # already assigned

    # original assignee can release
    client.post("/api/v1/auth/logout")
    _login(client, "p@example.com", "password123")
    r = client.post(f"/api/v1/chors/{chor_id}/unassign")
    assert r.status_code == 200
    assert r.json()["assignee_user_id"] is None


def test_unassigned_chors_listing(client):
    event = _make_event(client)
    client.post("/api/v1/auth/logout")
    me, _ = _make_parent_with_kids(client)

    r = client.get(f"/api/v1/events/{event['id']}/unassigned-chors")
    assert r.status_code == 200
    assert len(r.json()) == 18  # 3 days * 6


def test_create_activity_and_join(client):
    event = _make_event(client)
    client.post("/api/v1/auth/logout")
    me, kids = _make_parent_with_kids(client)
    day = event["days"][0]

    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/activities",
        json={"name": "Strandtur", "description": "Sandslot", "time": "14:00"},
    )
    assert r.status_code == 201, r.text
    activity = r.json()
    assert activity["created_by_user_id"] == me["id"]

    join = client.post(
        f"/api/v1/activities/{activity['id']}/attendees",
        json={"user_ids": [me["id"], kids[0]["id"]]},
    )
    assert join.status_code == 200
    assert set(join.json()["attendee_user_ids"]) == {me["id"], kids[0]["id"]}

    leave = client.delete(
        f"/api/v1/activities/{activity['id']}/attendees/{kids[0]['id']}"
    )
    assert leave.status_code == 204
    refresh = client.get(f"/api/v1/events/{event['id']}").json()
    act = refresh["days"][0]["activities"][0]
    assert kids[0]["id"] not in act["attendee_user_ids"]
