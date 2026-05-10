"""Family-scoped attendance: callers may pass explicit user_ids covering any
member of their family unit (parents and children).

The single-day and bulk endpoints accept `user_ids: list[int]`. When omitted,
behaviour is unchanged (caller + their own children).

Authorization:
- Non-admin: every id in `user_ids` must belong to the caller's family.
- Admin: any id is allowed.
"""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _make_couple(client) -> tuple[int, int, int, list[int]]:
    """Two parents in one family. Parent A has one child."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Karkov"}).json()["id"]
    ta = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "a@x.example.com"}
    ).json()["token"]
    tb = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "b@x.example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": ta, "name": "Anders", "password": "password123"},
    )
    a = client.get("/api/v1/auth/me").json()
    kid = client.post(
        "/api/v1/me/children",
        json={"name": "Liva", "birthdate": "2020-04-01"},
    ).json()
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": tb, "name": "Bente", "password": "password123"},
    )
    b = client.get("/api/v1/auth/me").json()
    client.post("/api/v1/auth/logout")
    return fid, a["id"], b["id"], [kid["id"]]


def _make_event(client) -> dict:
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e = client.post(
        "/api/v1/events",
        json={"name": "Karkov 2030", "start_date": "2030-07-10", "end_date": "2030-07-12"},
    ).json()
    client.post(f"/api/v1/events/{e['id']}/open")
    e = client.get(f"/api/v1/events/{e['id']}").json()
    client.post("/api/v1/auth/logout")
    return e


def test_attendance_accepts_explicit_user_ids_for_full_family(client):
    """Caller A signs up the whole family unit (A, B, kid) for a day."""
    event = _make_event(client)
    _, a_id, b_id, kids = _make_couple(client)
    _login(client, "a@x.example.com", "password123")

    day = event["days"][0]
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True, "user_ids": [a_id, b_id, kids[0]]},
    )
    assert r.status_code == 200, r.text
    assert set(r.json()["attendee_user_ids"]) == {a_id, b_id, kids[0]}


def test_attendance_can_deselect_some_family_members(client):
    """Caller signs everyone up, then resigns just the spouse (B)."""
    event = _make_event(client)
    _, a_id, b_id, kids = _make_couple(client)
    _login(client, "a@x.example.com", "password123")

    day = event["days"][0]
    client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True, "user_ids": [a_id, b_id, kids[0]]},
    )
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": False, "user_ids": [b_id]},
    )
    assert r.status_code == 200, r.text
    ids = set(r.json()["attendee_user_ids"])
    assert b_id not in ids
    assert {a_id, kids[0]}.issubset(ids)


def test_attendance_rejects_user_id_outside_family(client):
    event = _make_event(client)
    _, a_id, _, _ = _make_couple(client)

    # Other family parent
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    other_fid = client.post("/api/v1/families", json={"name": "Other"}).json()["id"]
    tok = client.post(
        f"/api/v1/families/{other_fid}/invites",
        json={"email": "out@x.example.com"},
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": tok, "name": "Out", "password": "password123"},
    )
    outsider_id = client.get("/api/v1/auth/me").json()["id"]
    client.post("/api/v1/auth/logout")

    _login(client, "a@x.example.com", "password123")
    day = event["days"][0]
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True, "user_ids": [a_id, outsider_id]},
    )
    assert r.status_code == 403, r.text


def test_default_attendance_unchanged_when_user_ids_omitted(client):
    """Backward compat: omitting user_ids keeps the existing self+kids behavior."""
    event = _make_event(client)
    _, a_id, b_id, kids = _make_couple(client)
    _login(client, "a@x.example.com", "password123")

    day = event["days"][0]
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True},
    )
    assert r.status_code == 200, r.text
    ids = set(r.json()["attendee_user_ids"])
    assert {a_id, kids[0]}.issubset(ids)
    assert b_id not in ids  # spouse not auto-included by default


def test_bulk_attendance_with_explicit_user_ids(client):
    event = _make_event(client)
    _, a_id, b_id, kids = _make_couple(client)
    _login(client, "a@x.example.com", "password123")

    day_ids = [d["id"] for d in event["days"][:2]]
    r = client.post(
        f"/api/v1/events/{event['id']}/attendance",
        json={
            "day_ids": day_ids,
            "present": True,
            "user_ids": [a_id, b_id, kids[0]],
        },
    )
    assert r.status_code == 200, r.text
    refreshed = client.get(f"/api/v1/events/{event['id']}").json()
    by_day = {d["id"]: set(d["attendee_user_ids"]) for d in refreshed["days"]}
    for day_id in day_ids:
        assert {a_id, b_id, kids[0]}.issubset(by_day[day_id])


def test_admin_can_attend_anyone(client):
    event = _make_event(client)
    _, a_id, _, _ = _make_couple(client)
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    day = event["days"][0]
    r = client.post(
        f"/api/v1/events/{event['id']}/days/{day['id']}/attendance",
        json={"present": True, "user_ids": [a_id]},
    )
    assert r.status_code == 200, r.text
    assert a_id in r.json()["attendee_user_ids"]
