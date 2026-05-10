"""Admin can delete chors from an event."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _bootstrap_event(client) -> dict:
    """Returns the created event JSON (logged in as admin)."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    return client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()


def _first_chor_id(event: dict) -> int:
    return event["days"][0]["chors"][0]["id"]


def test_admin_can_delete_chor(client):
    event = _bootstrap_event(client)
    chor_id = _first_chor_id(event)

    r = client.delete(f"/api/v1/chors/{chor_id}")
    assert r.status_code == 204, r.text

    refreshed = client.get(f"/api/v1/events/{event['id']}").json()
    chor_ids = {c["id"] for d in refreshed["days"] for c in d["chors"]}
    assert chor_id not in chor_ids


def test_non_admin_cannot_delete_chor(client):
    event = _bootstrap_event(client)
    chor_id = _first_chor_id(event)

    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "p@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "P", "password": "passpass1"},
    )

    r = client.delete(f"/api/v1/chors/{chor_id}")
    assert r.status_code == 403


def test_delete_missing_chor_is_idempotent(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.delete("/api/v1/chors/9999")
    assert r.status_code == 204


def test_delete_chor_does_not_break_linked_expense(client):
    event = _bootstrap_event(client)
    chor_id = _first_chor_id(event)
    client.post(f"/api/v1/events/{event['id']}/open")

    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "p@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "P", "password": "passpass1"},
    )
    for d in event["days"]:
        client.post(
            f"/api/v1/events/{event['id']}/days/{d['id']}/attendance",
            json={"present": True},
        )
    cats = {c["name"]: c["id"] for c in client.get("/api/v1/expense-categories").json()}
    expense_id = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 100, "chor_id": chor_id},
    ).json()["id"]
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.delete(f"/api/v1/chors/{chor_id}")
    assert r.status_code == 204, r.text

    expenses = client.get(f"/api/v1/events/{event['id']}/expenses").json()
    survivor = next(e for e in expenses if e["id"] == expense_id)
    assert survivor["chor_id"] is None
