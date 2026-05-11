"""Admin SMTP probe endpoint."""

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _login(client, email, password):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _bootstrap_parent(client, email="parent@example.com"):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    fid = client.post("/api/v1/families", json={"name": "TestFam"}).json()["id"]
    token = client.post(
        f"/api/v1/families/{fid}/invites", json={"email": email}
    ).json()["token"]
    client.post("/api/v1/auth/logout")
    client.post(
        "/api/v1/auth/register",
        json={"token": token, "name": "Forælder", "password": "password123"},
    )


def test_test_email_requires_auth(client):
    client.post("/api/v1/auth/logout")
    r = client.post("/api/v1/admin/test-email", json={"to": "x@example.com"})
    assert r.status_code == 401


def test_test_email_forbidden_for_non_admin(client):
    _bootstrap_parent(client)
    r = client.post(
        "/api/v1/admin/test-email", json={"to": "x@example.com"}
    )
    assert r.status_code == 403


def test_test_email_outbox_only_when_smtp_unconfigured(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/admin/test-email",
        json={"to": "probe@example.com", "subject": "Hello"},
    )
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["to"] == "probe@example.com"
    assert payload["subject"] == "Hello"
    assert payload["smtp_attempted"] is False
    assert payload["smtp_error"] is None
    assert isinstance(payload["outbox_id"], int)
    assert payload["outbox_id"] > 0


def test_test_email_default_subject_and_body(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post(
        "/api/v1/admin/test-email", json={"to": "probe@example.com"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["subject"] == "Karkov Weekend SMTP test"


def test_test_email_rejects_bad_email(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post("/api/v1/admin/test-email", json={"to": "not-an-email"})
    assert r.status_code == 422
