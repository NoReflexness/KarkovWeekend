"""Same-family parent can edit spouse and spouse's children profiles.

Rules:
- A parent in family X can PATCH another non-child user in family X (name,
  birthdate, email). Password changes are NOT allowed by spouse.
- Children in family X can be PATCHed by any parent in family X (existing
  rule, just covered for completeness).
- A parent CANNOT edit users from a different family.
"""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _make_couple(client) -> tuple[int, int, int, list[int]]:
    """Two parents in one family + one shared child via parent A.

    Returns (family_id, parent_a_id, parent_b_id, [child_id]).
    """
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


def test_spouse_can_edit_other_parent_profile(client):
    _, a_id, b_id, _ = _make_couple(client)
    _login(client, "a@x.example.com", "password123")
    r = client.patch(
        f"/api/v1/users/{b_id}",
        json={"name": "Bente Nyt", "birthdate": "1985-03-04"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Bente Nyt"
    assert body["birthdate"] == "1985-03-04"
    assert body["id"] == b_id
    assert a_id


def test_spouse_can_change_other_parent_email(client):
    _, _, b_id, _ = _make_couple(client)
    _login(client, "a@x.example.com", "password123")
    r = client.patch(
        f"/api/v1/users/{b_id}",
        json={"email": "bente-new@x.example.com"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "bente-new@x.example.com"


def test_spouse_cannot_change_other_parent_password(client):
    _, _, b_id, _ = _make_couple(client)
    _login(client, "a@x.example.com", "password123")
    r = client.patch(
        f"/api/v1/users/{b_id}",
        json={"password": "hijack-attempt-123"},
    )
    assert r.status_code == 403, r.text

    # Original password still works.
    client.post("/api/v1/auth/logout")
    assert _login(client, "b@x.example.com", "password123").status_code == 200


def test_spouse_can_edit_other_parents_child(client):
    _, _, _, kids = _make_couple(client)
    _login(client, "b@x.example.com", "password123")
    r = client.patch(
        f"/api/v1/children/{kids[0]}",
        json={"name": "Liva R."},
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Liva R."


def test_outsider_parent_cannot_edit(client):
    _, _, b_id, kids = _make_couple(client)

    # Outsider parent in a different family.
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    other = client.post("/api/v1/families", json={"name": "Other"}).json()["id"]
    tok = client.post(
        f"/api/v1/families/{other}/invites", json={"email": "out@x.example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": tok, "name": "Outsider", "password": "password123"},
    )

    r = client.patch(f"/api/v1/users/{b_id}", json={"name": "Hacked"})
    assert r.status_code == 403
    r2 = client.patch(f"/api/v1/children/{kids[0]}", json={"name": "Hacked"})
    assert r2.status_code == 403
