"""Admin edit-anything privileges across users, expenses, and families."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _bootstrap_parent(
    client,
    email: str = "parent@example.com",
    password: str = "password123",
    name: str = "Forælder",
    family_name: str = "TestFam",
) -> tuple[int, int]:
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": family_name}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": name, "password": password},
    )
    parent_id = client.get("/api/v1/auth/me").json()["id"]
    client.post("/api/v1/auth/logout")
    return fid, parent_id


def _setup_finalized_event_with_expense(client) -> tuple[int, int]:
    """Returns (event_id, expense_id) of an event whose budget is locked."""
    _, _ = _bootstrap_parent(client, email="payer@example.com", password="password123")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    event = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()
    client.post(f"/api/v1/events/{event['id']}/open")
    cats = {c["name"]: c["id"] for c in client.get("/api/v1/expense-categories").json()}
    client.post("/api/v1/auth/logout")

    _login(client, "payer@example.com", "password123")
    for d in event["days"]:
        client.post(
            f"/api/v1/events/{event['id']}/days/{d['id']}/attendance",
            json={"present": True},
        )
    expense_id = client.post(
        f"/api/v1/events/{event['id']}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 1500},
    ).json()["id"]
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post(f"/api/v1/events/{event['id']}/finalize")
    return event["id"], expense_id


# ---------- Admin can edit other users ----------

def test_admin_can_patch_any_user(client):
    _, parent_id = _bootstrap_parent(client)

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(
        f"/api/v1/users/{parent_id}",
        json={"name": "Ny Navn", "birthdate": "1980-01-01"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Ny Navn"
    assert body["birthdate"] == "1980-01-01"


def test_admin_can_change_user_email_and_password(client):
    _, parent_id = _bootstrap_parent(client, email="old@example.com", password="oldpass11")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(
        f"/api/v1/users/{parent_id}",
        json={"email": "new@example.com", "password": "newpass99"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "new@example.com"

    client.post("/api/v1/auth/logout")
    assert _login(client, "old@example.com", "oldpass11").status_code == 401
    assert _login(client, "new@example.com", "newpass99").status_code == 200


def test_admin_cannot_collide_email(client):
    _, p1 = _bootstrap_parent(client, email="a@example.com")
    _, _ = _bootstrap_parent(client, email="b@example.com", family_name="OtherFam")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(f"/api/v1/users/{p1}", json={"email": "b@example.com"})
    assert r.status_code == 400


def test_non_admin_cannot_patch_other_user(client):
    _, p1 = _bootstrap_parent(client, email="a@example.com")
    _, _ = _bootstrap_parent(client, email="b@example.com", family_name="OtherFam")

    _login(client, "b@example.com", "password123")
    r = client.patch(f"/api/v1/users/{p1}", json={"name": "Hacked"})
    assert r.status_code == 403


# ---------- Admin can edit / add / delete expenses on locked events ----------

def test_admin_can_edit_expense_on_locked_event(client):
    _, expense_id = _setup_finalized_event_with_expense(client)

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(
        f"/api/v1/expenses/{expense_id}",
        json={"amount_cents": 999, "description": "Justeret"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["amount_cents"] == 999
    assert r.json()["description"] == "Justeret"


def test_admin_can_delete_expense_on_locked_event(client):
    _, expense_id = _setup_finalized_event_with_expense(client)

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.delete(f"/api/v1/expenses/{expense_id}")
    assert r.status_code == 204


def test_admin_can_create_expense_on_locked_event(client):
    event_id, _ = _setup_finalized_event_with_expense(client)

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    cats = {c["name"]: c["id"] for c in client.get("/api/v1/expense-categories").json()}
    r = client.post(
        f"/api/v1/events/{event_id}/expenses",
        json={"category_id": cats["Mad"], "amount_cents": 200, "description": "Sent"},
    )
    assert r.status_code == 201, r.text


def test_non_admin_still_blocked_on_locked_event(client):
    _, expense_id = _setup_finalized_event_with_expense(client)

    _login(client, "payer@example.com", "password123")
    r = client.patch(
        f"/api/v1/expenses/{expense_id}", json={"amount_cents": 1}
    )
    assert r.status_code == 400
    r2 = client.delete(f"/api/v1/expenses/{expense_id}")
    assert r2.status_code == 400
