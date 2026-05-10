"""Event CRUD API tests."""

from datetime import date

import httpx

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _bootstrap_parent(client, email="parent@example.com"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "P", "password": "password123"},
    )
    return fid


def test_admin_can_create_event_with_days_and_chors(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    payload = {
        "name": "Karkov 2026",
        "description": "Sommertur",
        "address": "Ringkøbingvej 1, 6900 Skjern",
        "location_url": "https://www.google.com/maps?q=Skjern",
        "summerhouse_url": "https://example.com/sommerhus",
        "start_date": "2026-07-10",
        "end_date": "2026-07-13",
        "bed_count": 14,
    }
    r = client.post("/api/v1/events", json=payload)
    assert r.status_code == 201, r.text
    event = r.json()
    assert event["name"] == "Karkov 2026"
    assert event["status"] == "planlagt"
    assert len(event["days"]) == 4
    for d in event["days"]:
        assert len(d["chors"]) == 6


def test_parent_cannot_create_event(client):
    _bootstrap_parent(client)
    r = client.post(
        "/api/v1/events",
        json={"name": "x", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    )
    assert r.status_code == 403


def test_event_list_visible_to_all_logged_in(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    )
    client.post("/api/v1/auth/logout")

    _bootstrap_parent(client)
    r = client.get("/api/v1/events")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_next_event_endpoint(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(
        "/api/v1/events",
        json={"name": "Past", "start_date": "2020-01-01", "end_date": "2020-01-02"},
    )
    far = client.post(
        "/api/v1/events",
        json={"name": "Far Future", "start_date": "2099-12-30", "end_date": "2099-12-31"},
    ).json()
    near = client.post(
        "/api/v1/events",
        json={"name": "Soon", "start_date": "2030-01-01", "end_date": "2030-01-02"},
    ).json()

    r = client.get("/api/v1/events/next").json()
    assert r["id"] == near["id"]


def test_update_event_recreates_days(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()
    assert len(event["days"]) == 2

    upd = client.patch(
        f"/api/v1/events/{event['id']}",
        json={"end_date": "2026-07-13"},
    )
    assert upd.status_code == 200
    assert len(upd.json()["days"]) == 4


def test_open_for_attendance_changes_status(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()
    r = client.post(f"/api/v1/events/{event['id']}/open")
    assert r.status_code == 200
    assert r.json()["status"] == "aabent"


def test_event_includes_bed_demand_payload(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={
            "name": "Bed",
            "start_date": "2026-07-10",
            "end_date": "2026-07-11",
            "bed_count": 4,
        },
    ).json()
    assert event["bed_demand"] == {
        "bed_count": 4,
        "peak": 0,
        "peak_date": None,
    }
    for d in event["days"]:
        assert d["bed_demand"] == 0


def test_bed_demand_excludes_babies(client, monkeypatch):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "BedFam"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "bedparent@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Bed Parent", "password": "password123"},
    )
    me = client.get("/api/v1/auth/me").json()
    parent_id = me["id"]

    # bed_demand is computed against the EVENT date, not "today". Pick birthdates
    # so that on 2030-07-10 the baby is age 1 (BABY, excluded) and the kid is
    # age 8 (KID, counted).
    client.post(
        f"/api/v1/users/{parent_id}/children",
        json={"name": "Baby", "birthdate": "2029-07-10"},
    )
    client.post(
        f"/api/v1/users/{parent_id}/children",
        json={"name": "Kid", "birthdate": "2022-01-15"},
    )

    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={"name": "Beds", "start_date": "2030-07-10", "end_date": "2030-07-11", "bed_count": 5},
    ).json()
    client.post("/api/v1/auth/logout")

    _login(client, "bedparent@example.com", "password123")
    day_id = event["days"][0]["id"]
    client.post(
        f"/api/v1/events/{event['id']}/days/{day_id}/attendance",
        json={"present": True},
    )

    refreshed = client.get(f"/api/v1/events/{event['id']}").json()
    day_zero = next(d for d in refreshed["days"] if d["id"] == day_id)
    # Parent (1) + kid (1) = 2; baby excluded.
    assert day_zero["bed_demand"] == 2
    assert refreshed["bed_demand"]["peak"] == 2
    assert refreshed["bed_demand"]["peak_date"] == "2030-07-10"


def test_scrape_summerhouse_caches_result(client, monkeypatch):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={
            "name": "Scraped",
            "start_date": "2030-07-10",
            "end_date": "2030-07-11",
            "summerhouse_url": "https://example.com/sommerhus/123",
        },
    ).json()

    html = """
    <html><head>
      <meta property=\"og:title\" content=\"Lille Idyl ved Skagen\" />
      <meta property=\"og:description\" content=\"Hyggeligt sommerhus med 6 sovepladser og spa.\" />
      <meta property=\"og:image\" content=\"/images/hero.jpg\" />
    </head><body><h1>Lille Idyl ved Skagen</h1></body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, request=request)

    transport = httpx.MockTransport(handler)
    fake_client = httpx.Client(transport=transport, base_url="https://example.com")

    from app.services import scrape as scrape_module

    real_fetch = scrape_module.fetch_summerhouse

    def fake_fetch(url: str):
        return real_fetch(url, client=fake_client)

    monkeypatch.setattr("app.api.v1.events.fetch_summerhouse", fake_fetch)

    r = client.post(f"/api/v1/events/{event['id']}/scrape-summerhouse")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["summerhouse_title"] == "Lille Idyl ved Skagen"
    assert body["summerhouse_summary"].startswith("Hyggeligt sommerhus")
    assert body["summerhouse_image_url"] == "https://example.com/images/hero.jpg"
    assert body["summerhouse_scraped_at"] is not None


def test_scrape_requires_url(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={"name": "NoUrl", "start_date": "2030-07-10", "end_date": "2030-07-11"},
    ).json()
    r = client.post(f"/api/v1/events/{event['id']}/scrape-summerhouse")
    assert r.status_code == 400


def test_event_attendees_summary_lists_unique_users(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e = client.post(
        "/api/v1/events",
        json={"name": "Sommer", "start_date": "2030-07-10", "end_date": "2030-07-11"},
    ).json()
    client.post(f"/api/v1/events/{e['id']}/open")

    fa = client.post("/api/v1/families", json={"name": "Alfa"}).json()["id"]
    ta = client.post(
        f"/api/v1/families/{fa}/invites", json={"email": "alfa@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": ta, "name": "Anders", "password": "passpass1"},
    )
    me = client.get("/api/v1/auth/me").json()
    for d in e["days"]:
        client.post(
            f"/api/v1/events/{e['id']}/days/{d['id']}/attendance",
            json={"present": True},
        )

    detail = client.get(f"/api/v1/events/{e['id']}").json()
    summary = detail["attendees"]
    assert len(summary) == 1
    only = summary[0]
    assert only["user_id"] == me["id"]
    assert only["name"] == "Anders"
    assert only["family_id"] == fa
    assert only["family_name"] == "Alfa"
    assert only["days_attended"] == 2


def test_summerhouse_added_posts_system_message(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e = client.post(
        "/api/v1/events",
        json={"name": "UdenHus", "start_date": "2030-07-10", "end_date": "2030-07-11"},
    ).json()
    assert e["summerhouse_url"] is None

    before = client.get("/api/v1/chat/messages").json()
    n_before = len(before)

    r = client.patch(
        f"/api/v1/events/{e['id']}",
        json={"summerhouse_url": "https://example.com/saved-spot"},
    )
    assert r.status_code == 200, r.text

    after = client.get("/api/v1/chat/messages").json()
    new_msgs = after[n_before:]
    assert any(
        m["kind"] == "system"
        and "feriehus" in m["body"].lower()
        and "https://example.com/saved-spot" in m["body"]
        for m in new_msgs
    )

    # Updating the URL again should NOT re-fire the notification.
    n_mid = len(after)
    r2 = client.patch(
        f"/api/v1/events/{e['id']}",
        json={"summerhouse_url": "https://example.com/another"},
    )
    assert r2.status_code == 200
    after2 = client.get("/api/v1/chat/messages").json()
    new_msgs2 = after2[n_mid:]
    assert not any(
        m["kind"] == "system" and "feriehus" in m["body"].lower()
        for m in new_msgs2
    )


def test_invalid_date_range_rejected(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/events",
        json={"name": "x", "start_date": "2026-07-13", "end_date": "2026-07-10"},
    )
    assert r.status_code == 400
