"""Admin CRUD for expense categories + is_utility flag."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _bootstrap_parent(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Cats"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "p@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "P", "password": "password123"},
    )


def test_seed_marks_forbrug_as_utility(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    cats = client.get("/api/v1/expense-categories").json()
    forbrug = next(c for c in cats if c["name"] == "Forbrug")
    assert forbrug["is_utility"] is True
    udlejning = next(c for c in cats if c["name"] == "Udlejning")
    assert udlejning["is_utility"] is False


def test_admin_can_create_update_and_delete_category(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    created = client.post(
        "/api/v1/expense-categories",
        json={"name": "Vask", "is_per_person": True, "is_utility": True},
    )
    assert created.status_code == 201, created.text
    cat = created.json()
    assert cat["is_utility"] is True

    upd = client.patch(
        f"/api/v1/expense-categories/{cat['id']}",
        json={"is_utility": False, "name": "Rengøring"},
    )
    assert upd.status_code == 200
    assert upd.json()["is_utility"] is False
    assert upd.json()["name"] == "Rengøring"

    rm = client.delete(f"/api/v1/expense-categories/{cat['id']}")
    assert rm.status_code == 204


def test_non_admin_cannot_modify_categories(client):
    _bootstrap_parent(client)
    r = client.post(
        "/api/v1/expense-categories", json={"name": "Snack"}
    )
    assert r.status_code == 403
    r2 = client.patch(
        "/api/v1/expense-categories/1", json={"name": "Snack"}
    )
    assert r2.status_code == 403
    r3 = client.delete("/api/v1/expense-categories/1")
    assert r3.status_code == 403


def test_cannot_delete_category_with_expenses(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    cat = client.post(
        "/api/v1/expense-categories", json={"name": "Slik"}
    ).json()
    e = client.post(
        "/api/v1/events",
        json={"name": "E", "start_date": "2030-07-10", "end_date": "2030-07-11"},
    ).json()
    client.post(
        f"/api/v1/events/{e['id']}/expenses",
        json={"category_id": cat["id"], "amount_cents": 1500, "description": "Lakrids"},
    )
    r = client.delete(f"/api/v1/expense-categories/{cat['id']}")
    assert r.status_code == 400


def test_duplicate_category_name_rejected(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    client.post("/api/v1/expense-categories", json={"name": "Brænde"})
    r = client.post("/api/v1/expense-categories", json={"name": "Brænde"})
    assert r.status_code == 400


def test_patch_to_existing_name_rejected(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    a = client.post("/api/v1/expense-categories", json={"name": "Olie"}).json()
    client.post("/api/v1/expense-categories", json={"name": "Pellets"})
    r = client.patch(
        f"/api/v1/expense-categories/{a['id']}", json={"name": "Pellets"}
    )
    assert r.status_code == 400
