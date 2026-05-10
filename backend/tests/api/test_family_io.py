"""Family import/export (YAML).

Goals:
- Admin can dump all families/users/children to YAML (no passwords/tokens).
- Admin can import the same YAML on a fresh DB and reconstitute the data.
- Re-importing the same file is idempotent (existing rows are skipped).
- Non-admin is forbidden.
"""

import yaml

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _seed_two_families(client) -> dict:
    """Create two families with parents (via invite + register) and a child."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fa = client.post("/api/v1/families", json={"name": "Alfa"}).json()["id"]
    ta = client.post(
        f"/api/v1/families/{fa}/invites", json={"email": "alfa@example.com"}
    ).json()["token"]
    fb = client.post("/api/v1/families", json={"name": "Beta"}).json()["id"]
    tb = client.post(
        f"/api/v1/families/{fb}/invites", json={"email": "beta@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": ta, "name": "Anders", "password": "passpass1"},
    )
    me_a = client.get("/api/v1/auth/me").json()
    client.post(
        f"/api/v1/users/{me_a['id']}/children",
        json={"name": "Liva", "birthdate": "2020-04-01"},
    )
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/register",
        json={"token": tb, "name": "Bente", "password": "passpass2"},
    )
    client.post("/api/v1/auth/logout")
    return {"fa": fa, "fb": fb}


def test_export_yaml_dumps_all_families_without_passwords(client):
    _seed_two_families(client)
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.get("/api/v1/admin/families/export")
    assert r.status_code == 200, r.text
    assert "yaml" in r.headers.get("content-type", "")
    data = yaml.safe_load(r.text)
    assert "families" in data
    names = sorted(f["name"] for f in data["families"])
    assert "Alfa" in names and "Beta" in names

    blob = r.text.lower()
    assert "password" not in blob
    assert "password_hash" not in blob

    alfa = next(f for f in data["families"] if f["name"] == "Alfa")
    assert any(m.get("email") == "alfa@example.com" for m in alfa["members"])
    parent = next(m for m in alfa["members"] if m.get("email") == "alfa@example.com")
    children_names = [c["name"] for c in (parent.get("children") or [])]
    assert "Liva" in children_names


def test_non_admin_cannot_export_or_import(client):
    fids = _seed_two_families(client)
    assert fids
    _login(client, "alfa@example.com", "passpass1")
    assert client.get("/api/v1/admin/families/export").status_code == 403
    r = client.post(
        "/api/v1/admin/families/import",
        json={"yaml": "families: []"},
    )
    assert r.status_code == 403


def test_import_creates_families_users_and_children(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    payload = {
        "yaml": yaml.safe_dump(
            {
                "families": [
                    {
                        "name": "Karkov",
                        "members": [
                            {
                                "name": "Mads",
                                "email": "mads@imp.example.com",
                                "birthdate": "1985-05-04",
                                "role": "parent",
                                "notify_email": True,
                                "children": [
                                    {"name": "Liva", "birthdate": "2020-04-01"},
                                    {"name": "Storm", "birthdate": "2022-09-12"},
                                ],
                            },
                            {
                                "name": "Mor",
                                "email": "mor@imp.example.com",
                                "role": "parent",
                            },
                        ],
                    },
                    {
                        "name": "Andet",
                        "members": [
                            {"name": "Solo", "email": "solo@imp.example.com"},
                        ],
                    },
                ]
            }
        )
    }
    r = client.post("/api/v1/admin/families/import", json=payload)
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["families_created"] == 2
    assert summary["parents_created"] == 3
    assert summary["children_created"] == 2

    fams = client.get("/api/v1/families").json()
    fam_names = {f["name"] for f in fams}
    assert {"Karkov", "Andet"}.issubset(fam_names)


def test_import_does_not_set_passwords_so_user_cannot_login(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    yml = yaml.safe_dump(
        {
            "families": [
                {
                    "name": "Lockout",
                    "members": [
                        {
                            "name": "NewParent",
                            "email": "new-parent@imp.example.com",
                            "role": "parent",
                        }
                    ],
                }
            ]
        }
    )
    r = client.post("/api/v1/admin/families/import", json={"yaml": yml})
    assert r.status_code == 200, r.text
    client.post("/api/v1/auth/logout")
    bad = client.post(
        "/api/v1/auth/login",
        json={"email": "new-parent@imp.example.com", "password": "anything-here"},
    )
    assert bad.status_code == 401


def test_import_is_idempotent_on_second_run(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    yml = yaml.safe_dump(
        {
            "families": [
                {
                    "name": "Idem",
                    "members": [
                        {
                            "name": "Once",
                            "email": "once@imp.example.com",
                            "role": "parent",
                            "children": [{"name": "Junior", "birthdate": "2024-01-01"}],
                        }
                    ],
                }
            ]
        }
    )
    first = client.post(
        "/api/v1/admin/families/import", json={"yaml": yml}
    ).json()
    second = client.post(
        "/api/v1/admin/families/import", json={"yaml": yml}
    ).json()
    assert first["families_created"] == 1
    assert second["families_created"] == 0
    assert second["parents_created"] == 0
    assert second["children_created"] == 0
    assert second["skipped"]["families"] >= 1


def test_export_then_import_into_fresh_state_is_idempotent(client):
    _seed_two_families(client)
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    dump = client.get("/api/v1/admin/families/export").text

    # Re-import the same dump on top of itself; nothing new should be created.
    r = client.post("/api/v1/admin/families/import", json={"yaml": dump})
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["families_created"] == 0
    assert summary["parents_created"] == 0
    assert summary["children_created"] == 0


def test_import_rejects_bad_yaml(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/admin/families/import", json={"yaml": "this: is\n  not: [valid"}
    )
    assert r.status_code == 400


def test_import_rejects_missing_family_name(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    yml = yaml.safe_dump({"families": [{"members": []}]})
    r = client.post("/api/v1/admin/families/import", json={"yaml": yml})
    assert r.status_code == 400
