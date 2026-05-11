"""Auth API tests.

Flows covered:
- admin login (seeded admin)
- admin creates a family
- admin invites a parent (writes to outbox, returns invite token)
- parent registers via invite token
- parent logs in, calls /me
- forgot password / reset password roundtrip via outbox
"""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_admin_login_success(client):
    r = _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["user"]["email"] == ADMIN_EMAIL
    assert data["user"]["role"] == "admin"
    # cookie should be set on the client
    assert any(c.name == "access_token" for c in client.cookies.jar)


def test_admin_login_wrong_password(client):
    r = _login(client, ADMIN_EMAIL, "nope")
    assert r.status_code == 401


def test_me_requires_auth(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_me_returns_logged_in_user(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == ADMIN_EMAIL


def test_logout_clears_cookie(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    assert client.get("/api/v1/auth/me").status_code == 200
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    # client.cookies should not contain access_token anymore
    assert client.get("/api/v1/auth/me").status_code == 401


def test_full_invite_flow(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)

    fam_resp = client.post("/api/v1/families", json={"name": "Karkov"})
    assert fam_resp.status_code == 201, fam_resp.text
    family_id = fam_resp.json()["id"]

    invite = client.post(
        "/api/v1/families/{}/invites".format(family_id),
        json={"email": "newparent@example.com"},
    )
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]
    assert token

    # Logout admin so the new parent can register cleanly
    client.post("/api/v1/auth/logout")

    reg = client.post(
        "/api/v1/auth/register",
        json={
            "token": token,
            "name": "Ny Forælder",
            "password": "supersecret123",
        },
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["email"] == "newparent@example.com"

    login = _login(client, "newparent@example.com", "supersecret123")
    assert login.status_code == 200
    me = client.get("/api/v1/auth/me").json()
    assert me["family_id"] == family_id
    assert me["role"] == "parent"


def test_invite_token_rejected_twice(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    family_id = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{family_id}/invites", json={"email": "x@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")

    first = client.post(
        "/api/v1/auth/register", json={"token": token, "name": "X", "password": "password1"}
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/auth/register", json={"token": token, "name": "Y", "password": "password2"}
    )
    assert second.status_code == 400


def test_forgot_password_creates_outbox_entry(client):
    r = client.post("/api/v1/auth/forgot-password", json={"email": ADMIN_EMAIL})
    assert r.status_code == 204

    # Look in DB outbox via debug endpoint? Easier: trigger reset using the token from response.
    # We expose the token via the outbox row -> we need a debug helper. Fetch latest outbox via API.
    debug = client.get("/api/v1/_debug/last-email")
    assert debug.status_code == 200
    body = debug.json()["body"]
    # token shows up in URL ?token=...
    assert "token=" in body
    token = body.split("token=")[1].splitlines()[0].strip()

    new_pw = "brand-new-password-123"
    reset = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "new_password": new_pw}
    )
    assert reset.status_code == 204

    # old password no longer works
    assert _login(client, ADMIN_EMAIL, ADMIN_PASSWORD).status_code == 401
    assert _login(client, ADMIN_EMAIL, new_pw).status_code == 200


def test_invite_does_not_notify_by_default(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Stille"}).json()["id"]
    inv = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "quiet@example.com"}
    )
    assert inv.status_code == 201
    assert inv.json()["notified_at"] is None
    pending = client.get(f"/api/v1/families/{fid}/invites").json()
    assert [p["email"] for p in pending] == ["quiet@example.com"]
    assert pending[0]["notified_at"] is None


def test_send_pending_invites_marks_notified(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Bulk"}).json()["id"]
    client.post(f"/api/v1/families/{fid}/invites", json={"email": "a@example.com"})
    client.post(f"/api/v1/families/{fid}/invites", json={"email": "b@example.com"})

    res = client.post(f"/api/v1/families/{fid}/invites/send-pending")
    assert res.status_code == 200
    body = res.json()
    assert body["sent"] == 2

    again = client.post(f"/api/v1/families/{fid}/invites/send-pending").json()
    assert again["sent"] == 0


def test_invite_with_notify_true_sends_email(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Now"}).json()["id"]
    inv = client.post(
        f"/api/v1/families/{fid}/invites",
        json={"email": "now@example.com", "notify": True},
    )
    assert inv.status_code == 201
    assert inv.json()["notified_at"] is not None


def test_resend_invite_works_even_after_notified(client):
    """Bulk send-pending marked the invite as notified, but SMTP silently
    failed (pre-fix). The per-invite resend endpoint must still deliver."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Resend"}).json()["id"]
    inv = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "a@example.com"}
    ).json()
    assert inv["notified_at"] is None

    # Pretend a bulk send happened (marks notified_at).
    client.post(f"/api/v1/families/{fid}/invites/send-pending")
    after_bulk = client.get(f"/api/v1/families/{fid}/invites").json()
    assert after_bulk[0]["notified_at"] is not None
    first_notified = after_bulk[0]["notified_at"]

    # Single resend still works and bumps notified_at.
    r = client.post(
        f"/api/v1/families/{fid}/invites/{inv['id']}/resend"
    )
    assert r.status_code == 200, r.text
    assert r.json()["notified_at"] is not None
    assert r.json()["notified_at"] >= first_notified


def test_resend_invite_rejects_used_invite(client):
    """Used tokens are burned — resending would be a no-op confusing UX."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Used"}).json()["id"]
    inv = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "used@example.com"}
    ).json()
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": inv["token"], "name": "U", "password": "password123"},
    )
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(f"/api/v1/families/{fid}/invites/{inv['id']}/resend")
    assert r.status_code == 400


def test_resend_invite_requires_admin(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Auth"}).json()["id"]
    invite_token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "x@example.com"}
    ).json()["token"]
    parent_invite_token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "y@example.com"}
    ).json()
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": invite_token, "name": "P", "password": "password123"},
    )
    r = client.post(
        f"/api/v1/families/{fid}/invites/{parent_invite_token['id']}/resend"
    )
    assert r.status_code == 403


def test_admin_can_promote_and_demote_user(client):
    # bootstrap a parent
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "Promo"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "promo@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    parent_id = client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Promo P", "password": "passpass1"},
    ).json()["id"]
    client.post("/api/v1/auth/logout")

    # admin promotes
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.patch(f"/api/v1/users/{parent_id}/role", json={"role": "admin"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"

    # demote back
    r2 = client.patch(f"/api/v1/users/{parent_id}/role", json={"role": "parent"})
    assert r2.status_code == 200
    assert r2.json()["role"] == "parent"


def test_admin_cannot_demote_last_admin(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    me = client.get("/api/v1/auth/me").json()
    r = client.patch(f"/api/v1/users/{me['id']}/role", json={"role": "parent"})
    assert r.status_code == 400


def test_non_admin_cannot_change_role(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "NA"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "na@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    parent_id = client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "NA P", "password": "passpass1"},
    ).json()["id"]

    r = client.patch(f"/api/v1/users/{parent_id}/role", json={"role": "admin"})
    assert r.status_code == 403


def test_only_admin_can_create_family(client):
    # create a parent
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "F"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": "p@example.com"}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register", json={"token": token, "name": "P", "password": "passpass1"}
    )
    _login(client, "p@example.com", "passpass1")

    r = client.post("/api/v1/families", json={"name": "Other"})
    assert r.status_code == 403
