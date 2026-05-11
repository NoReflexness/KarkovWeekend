"""User / child / profile picture API tests."""

import io

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, password):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _bootstrap_parent(client, email="parent@example.com", password="password123"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "TestFam"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Forælder", "password": password},
    )
    return fid


def test_patch_me_updates_name(client):
    _bootstrap_parent(client)
    r = client.patch("/api/v1/me", json={"name": "Ny Navn"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Ny Navn"


def test_change_password_self_service(client):
    _bootstrap_parent(client)
    r = client.post(
        "/api/v1/me/change-password",
        json={"current_password": "password123", "new_password": "newpass456"},
    )
    assert r.status_code == 204
    client.post("/api/v1/auth/logout")
    assert _login(client, "parent@example.com", "password123").status_code == 401
    assert _login(client, "parent@example.com", "newpass456").status_code == 200


def test_create_list_update_delete_child(client):
    _bootstrap_parent(client)

    create = client.post(
        "/api/v1/me/children",
        json={"name": "Lille Liva", "birthdate": "2020-04-01"},
    )
    assert create.status_code == 201, create.text
    child = create.json()
    assert child["role"] == "child"
    assert child["birthdate"] == "2020-04-01"
    assert child["parent_user_id"] is not None

    listing = client.get("/api/v1/me/children").json()
    assert len(listing) == 1

    update = client.patch(
        f"/api/v1/children/{child['id']}", json={"name": "Liva"}
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Liva"

    delete = client.delete(f"/api/v1/children/{child['id']}")
    assert delete.status_code == 204
    assert client.get("/api/v1/me/children").json() == []


def test_parent_cannot_modify_other_familys_child(client):
    # parent A creates child
    _bootstrap_parent(client, email="a@example.com")
    child_id = client.post(
        "/api/v1/me/children", json={"name": "K", "birthdate": "2018-01-01"}
    ).json()["id"]
    client.post("/api/v1/auth/logout")

    # parent B in a different family
    _bootstrap_parent(client, email="b@example.com")
    r = client.patch(f"/api/v1/children/{child_id}", json={"name": "Hacked"})
    assert r.status_code == 403


def test_admin_can_modify_any_child(client):
    _bootstrap_parent(client)
    child_id = client.post(
        "/api/v1/me/children", json={"name": "K", "birthdate": "2018-01-01"}
    ).json()["id"]
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(f"/api/v1/children/{child_id}", json={"name": "Admin Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Admin Renamed"


def test_profile_picture_upload(client):
    _bootstrap_parent(client)
    # 1x1 transparent PNG
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
        "890000000d49444154789c63000100000005000100"
        "0000000049454e44ae426082"
    )
    r = client.post(
        "/api/v1/me/profile-picture",
        files={"file": ("avatar.png", io.BytesIO(png), "image/png")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile_picture_url"].endswith(".png")
    me = client.get("/api/v1/auth/me").json()
    assert me["profile_picture_url"] is not None


_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c63000100000005000100"
    "0000000049454e44ae426082"
)


def _png_files(name="avatar.png"):
    return {"file": (name, io.BytesIO(_PNG_1X1), "image/png")}


def test_family_picture_upload_by_member(client):
    fid = _bootstrap_parent(client)
    r = client.post(f"/api/v1/families/{fid}/profile-picture", files=_png_files("fam.png"))
    assert r.status_code == 200, r.text
    assert r.json()["profile_picture_url"].endswith(".png")


def test_family_picture_upload_other_family_forbidden(client):
    fid_a = _bootstrap_parent(client, email="a@example.com")
    client.post("/api/v1/auth/logout")
    _bootstrap_parent(client, email="b@example.com")
    r = client.post(f"/api/v1/families/{fid_a}/profile-picture", files=_png_files())
    assert r.status_code == 403


def test_child_picture_upload_by_parent(client):
    _bootstrap_parent(client)
    child_id = client.post(
        "/api/v1/me/children", json={"name": "Liva", "birthdate": "2020-04-01"}
    ).json()["id"]
    r = client.post(
        f"/api/v1/children/{child_id}/profile-picture", files=_png_files("liva.png")
    )
    assert r.status_code == 200, r.text
    assert r.json()["profile_picture_url"].endswith(".png")


def test_child_picture_upload_other_family_forbidden(client):
    _bootstrap_parent(client, email="a@example.com")
    child_id = client.post(
        "/api/v1/me/children", json={"name": "K", "birthdate": "2018-01-01"}
    ).json()["id"]
    client.post("/api/v1/auth/logout")
    _bootstrap_parent(client, email="b@example.com")
    r = client.post(f"/api/v1/children/{child_id}/profile-picture", files=_png_files())
    assert r.status_code == 403


def test_child_picture_upload_admin_can_override(client):
    _bootstrap_parent(client)
    child_id = client.post(
        "/api/v1/me/children", json={"name": "K", "birthdate": "2018-01-01"}
    ).json()["id"]
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(f"/api/v1/children/{child_id}/profile-picture", files=_png_files())
    assert r.status_code == 200


def test_admin_can_create_child_for_a_parent(client):
    fid = _bootstrap_parent(client)
    parent_id = client.get("/api/v1/auth/me").json()["id"]
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(
        f"/api/v1/users/{parent_id}/children",
        json={"name": "Admin Made", "birthdate": "2019-06-01"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["family_id"] == fid


def test_pricing_rules_admin_only(client):
    _bootstrap_parent(client)
    r = client.patch("/api/v1/pricing-rules", json={"baby_max_age": 3, "kid_max_age": 14})
    assert r.status_code == 403

    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch("/api/v1/pricing-rules", json={"baby_max_age": 1, "kid_max_age": 12})
    assert r.status_code == 200
    assert r.json() == {"baby_max_age": 1, "kid_max_age": 12}

    g = client.get("/api/v1/pricing-rules").json()
    assert g["baby_max_age"] == 1


def test_list_users_admin_sees_all(client):
    fid = _bootstrap_parent(client, email="alice@example.com")
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.get("/api/v1/users")
    assert r.status_code == 200, r.text
    emails = {u["email"] for u in r.json() if u["email"]}
    assert ADMIN_EMAIL in emails
    assert "alice@example.com" in emails

    r2 = client.get("/api/v1/users", params={"family_id": fid})
    assert r2.status_code == 200
    fam_emails = {u["email"] for u in r2.json() if u["email"]}
    assert "alice@example.com" in fam_emails
    assert ADMIN_EMAIL not in fam_emails


def test_list_users_parent_sees_only_own_family(client):
    _bootstrap_parent(client, email="b@example.com")
    r = client.get("/api/v1/users", params={"role": "parent"})
    assert r.status_code == 200
    emails = {u["email"] for u in r.json() if u["email"]}
    assert emails == {"b@example.com"}


def test_admin_can_attach_self_to_family(client):
    """Admins start without a family. Admin can PATCH their own family_id."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    me = client.get("/api/v1/auth/me").json()
    assert me["family_id"] is None
    fid = client.post("/api/v1/families", json={"name": "Hjem"}).json()["id"]

    r = client.patch(f"/api/v1/users/{me['id']}", json={"family_id": fid})
    assert r.status_code == 200, r.text
    assert r.json()["family_id"] == fid


def test_admin_can_detach_user_with_null_family_id(client):
    _bootstrap_parent(client)
    me = client.get("/api/v1/auth/me").json()
    assert me["family_id"] is not None
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(f"/api/v1/users/{me['id']}", json={"family_id": None})
    assert r.status_code == 200, r.text
    assert r.json()["family_id"] is None


def test_admin_family_id_change_cascades_to_children(client):
    _bootstrap_parent(client)
    me = client.get("/api/v1/auth/me").json()
    child = client.post(
        "/api/v1/me/children", json={"name": "K", "birthdate": "2018-01-01"}
    ).json()
    assert child["family_id"] == me["family_id"]
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    other = client.post("/api/v1/families", json={"name": "Anden"}).json()["id"]
    r = client.patch(f"/api/v1/users/{me['id']}", json={"family_id": other})
    assert r.status_code == 200, r.text

    # Child must follow the parent into the new family.
    refreshed_kids = client.get(
        f"/api/v1/users?family_id={other}"
    ).json()
    assert any(u["id"] == child["id"] for u in refreshed_kids)


def test_admin_family_id_unknown_family_404(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    me = client.get("/api/v1/auth/me").json()
    r = client.patch(f"/api/v1/users/{me['id']}", json={"family_id": 99999})
    assert r.status_code == 404


def test_non_admin_cannot_change_family_id(client):
    """A parent can edit a same-family spouse's name, but not their family_id."""
    _bootstrap_parent(client, email="a@example.com")
    me = client.get("/api/v1/auth/me").json()
    client.post("/api/v1/auth/logout")

    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid2 = client.post("/api/v1/families", json={"name": "Anden"}).json()["id"]
    invite_token = client.post(
        f"/api/v1/families/{me['family_id']}/invites", json={"email": "b@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": invite_token, "name": "B", "password": "password123"},
    )
    # `b` is logged in as a regular parent in the same family as `me`.
    r = client.patch(f"/api/v1/users/{me['id']}", json={"family_id": fid2})
    assert r.status_code == 403


def test_list_expense_categories(client):
    _bootstrap_parent(client)
    r = client.get("/api/v1/expense-categories")
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert {"Udlejning", "Forbrug", "Mad", "Aktiviteter", "Andet"} <= set(names)
