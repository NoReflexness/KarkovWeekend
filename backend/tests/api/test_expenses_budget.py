"""Expenses + budget endpoint integration tests."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _setup_event_two_families(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()
    client.post(f"/api/v1/events/{e['id']}/open")

    fa = client.post("/api/v1/families", json={"name": "A"}).json()["id"]
    fb = client.post("/api/v1/families", json={"name": "B"}).json()["id"]

    ta = client.post(
        f"/api/v1/families/{fa}/invites", json={"email": "a@example.com"}
    ).json()["token"]
    tb = client.post(
        f"/api/v1/families/{fb}/invites", json={"email": "b@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": ta, "name": "A", "password": "passpass1"},
    )
    me_a = client.get("/api/v1/auth/me").json()
    for d in e["days"]:
        client.post(
            f"/api/v1/events/{e['id']}/days/{d['id']}/attendance",
            json={"present": True},
        )
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": tb, "name": "B", "password": "passpass1"},
    )
    me_b = client.get("/api/v1/auth/me").json()
    for d in e["days"]:
        client.post(
            f"/api/v1/events/{e['id']}/days/{d['id']}/attendance",
            json={"present": True},
        )

    return e, me_a, me_b


def _categories(client) -> dict[str, int]:
    return {c["name"]: c["id"] for c in client.get("/api/v1/expense-categories").json()}


def test_create_and_list_expense(client):
    event, _, me_b = _setup_event_two_families(client)
    cat_id = _categories(client)["Mad"]

    r = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={
            "category_id": cat_id,
            "amount_cents": 1500,
            "description": "Indkøb",
        },
    )
    assert r.status_code == 201, r.text
    expense = r.json()
    assert expense["paid_by_user_id"] == me_b["id"]
    assert expense["amount_cents"] == 1500

    listing = client.get(f"/api/v1/events/{event['id']}/expenses").json()
    assert len(listing) == 1


def test_budget_endpoint_returns_balance(client):
    event, me_a, me_b = _setup_event_two_families(client)
    cats = _categories(client)

    # Login as A and pay 2000 for Mad
    client.post("/api/v1/auth/logout")
    _login(client, "a@example.com", "passpass1")
    client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 2000},
    )

    # Login as B and pay 1000 for Udlejning
    client.post("/api/v1/auth/logout")
    _login(client, "b@example.com", "passpass1")
    client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Udlejning"], "amount_cents": 1000},
    )

    budget = client.get(f"/api/v1/events/{event['id']}/budget").json()
    assert budget["total_cents"] == 3000
    by_user = {s["user_id"]: s for s in budget["shares"]}
    # Both adults attended both days. Each pays 1500.
    assert by_user[me_a["id"]]["share_cents"] == 1500
    assert by_user[me_b["id"]]["share_cents"] == 1500
    # A paid 2000 (net +500), B paid 1000 (net -500)
    assert by_user[me_a["id"]]["net_cents"] == 500
    assert by_user[me_b["id"]]["net_cents"] == -500
    settlements = budget["settlements"]
    assert len(settlements) == 1
    assert settlements[0]["amount_cents"] == 500


def test_child_cannot_create_expense(client):
    event, me_a, _ = _setup_event_two_families(client)
    cats = _categories(client)
    client.post("/api/v1/auth/logout")
    _login(client, "a@example.com", "passpass1")
    child = client.post(
        "/api/v1/me/children",
        json={"name": "Kid", "birthdate": "2018-04-01", "email": "kid@example.com",
              "password": "kidpass1"},
    ).json()
    client.post("/api/v1/auth/logout")
    _login(client, "kid@example.com", "kidpass1")
    r = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 100},
    )
    assert r.status_code == 403


def test_child_cannot_view_budget(client):
    event, _, _ = _setup_event_two_families(client)
    client.post("/api/v1/auth/logout")
    _login(client, "a@example.com", "passpass1")
    client.post(
        "/api/v1/me/children",
        json={"name": "Kid", "birthdate": "2018-04-01",
              "email": "kid@example.com", "password": "kidpass1"},
    )
    client.post("/api/v1/auth/logout")
    _login(client, "kid@example.com", "kidpass1")
    r = client.get(f"/api/v1/events/{event['id']}/budget")
    assert r.status_code == 403


def test_expense_includes_payer_name(client):
    event, _, me_b = _setup_event_two_families(client)
    cats = _categories(client)
    client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 1500},
    )
    listing = client.get(f"/api/v1/events/{event['id']}/expenses").json()
    assert listing[0]["paid_by_user_name"] == me_b["name"]


def test_admin_can_change_expense_payer(client):
    event, me_a, me_b = _setup_event_two_families(client)
    cats = _categories(client)
    client.post("/api/v1/auth/logout")
    _login(client, "a@example.com", "passpass1")
    expense_id = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 500},
    ).json()["id"]

    # Other parent cannot reassign payer.
    client.post("/api/v1/auth/logout")
    _login(client, "b@example.com", "passpass1")
    r = client.patch(
        f"/api/v1/expenses/{expense_id}", json={"paid_by_user_id": me_b["id"]}
    )
    assert r.status_code == 403

    # Admin can.
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(
        f"/api/v1/expenses/{expense_id}", json={"paid_by_user_id": me_b["id"]}
    )
    assert r.status_code == 200, r.text
    assert r.json()["paid_by_user_id"] == me_b["id"]
    assert r.json()["paid_by_user_name"] == me_b["name"]

    # Reassigning to a child is rejected.
    _login(client, "a@example.com", "passpass1")
    kid = client.post(
        "/api/v1/me/children",
        json={
            "name": "Kid",
            "birthdate": "2018-04-01",
            "email": "kid2@example.com",
            "password": "kidpass1",
        },
    ).json()
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(
        f"/api/v1/expenses/{expense_id}", json={"paid_by_user_id": kid["id"]}
    )
    assert r.status_code == 400


def test_delete_expense_only_by_payer_or_admin(client):
    event, me_a, me_b = _setup_event_two_families(client)
    cats = _categories(client)
    client.post("/api/v1/auth/logout")
    _login(client, "a@example.com", "passpass1")
    expense_id = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 500},
    ).json()["id"]

    client.post("/api/v1/auth/logout")
    _login(client, "b@example.com", "passpass1")
    r = client.delete(f"/api/v1/expenses/{expense_id}")
    assert r.status_code == 403

    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.delete(f"/api/v1/expenses/{expense_id}")
    assert r.status_code == 204
