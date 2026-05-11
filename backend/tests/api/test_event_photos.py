"""Event photo upload, gallery, group-photo invariant, and authz tests."""

import io
from datetime import date

from PIL import Image

ADMIN_EMAIL = "admin@karkov.example.com"
ADMIN_PASSWORD = "admin-test-password"


def _png_bytes(*, width: int = 4, height: int = 4) -> bytes:
    """Generate a valid PNG via Pillow itself, so the upload service can
    actually decode it. The minimal hex blob used elsewhere in the suite is
    accepted as raw bytes by the avatar endpoint, but `save_event_photo`
    re-decodes via Pillow and rejects malformed input."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(180, 90, 60)).save(buf, format="PNG")
    return buf.getvalue()


def _login(client, email, pw):
    return client.post("/api/v1/auth/login", json={"email": email, "password": pw})


def _files(name="photo.png"):
    return [("files", (name, io.BytesIO(_png_bytes()), "image/png"))]


def _files_multi(n: int):
    return [
        ("files", (f"p{i}.png", io.BytesIO(_png_bytes()), "image/png"))
        for i in range(n)
    ]


def _bootstrap_event(client) -> int:
    """Admin-created event so tests have something to upload to."""
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    payload = {
        "name": "Photo Test",
        "start_date": "2026-07-10",
        "end_date": "2026-07-11",
    }
    return client.post("/api/v1/events", json=payload).json()["id"]


def _bootstrap_parent_in_family(client, email="parent@example.com"):
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


def test_upload_single_photo(client):
    eid = _bootstrap_event(client)
    r = client.post(f"/api/v1/events/{eid}/photos", files=_files())
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 1
    photo = body[0]
    assert photo["event_id"] == eid
    assert photo["url"].startswith("/uploads/events/")
    assert photo["url"].endswith(".png")
    assert photo["is_group_photo"] is False
    assert photo["width"] == 4
    assert photo["height"] == 4


def test_upload_multiple_photos_in_one_request(client):
    """Batch upload — drop a whole album in one go."""
    eid = _bootstrap_event(client)
    r = client.post(f"/api/v1/events/{eid}/photos", files=_files_multi(3))
    assert r.status_code == 201, r.text
    body = r.json()
    assert len(body) == 3
    urls = [p["url"] for p in body]
    assert len(set(urls)) == 3, "every photo gets its own URL"


def test_list_photos_orders_group_photo_first(client):
    eid = _bootstrap_event(client)
    p1 = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    p2 = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    p3 = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]

    # Mark the SECOND upload as group photo. List should still surface it first.
    client.patch(
        f"/api/v1/events/{eid}/photos/{p2['id']}",
        json={"is_group_photo": True},
    )

    listing = client.get(f"/api/v1/events/{eid}/photos").json()
    assert [p["id"] for p in listing] == [p2["id"], p1["id"], p3["id"]]


def test_set_group_photo_unsets_previous_one(client):
    """Exactly one group photo per event — flipping the flag must clear others."""
    eid = _bootstrap_event(client)
    p1 = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    p2 = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]

    client.patch(
        f"/api/v1/events/{eid}/photos/{p1['id']}",
        json={"is_group_photo": True},
    )
    client.patch(
        f"/api/v1/events/{eid}/photos/{p2['id']}",
        json={"is_group_photo": True},
    )

    listing = client.get(f"/api/v1/events/{eid}/photos").json()
    flags = {p["id"]: p["is_group_photo"] for p in listing}
    assert flags[p1["id"]] is False
    assert flags[p2["id"]] is True


def test_event_out_surfaces_group_photo_url_and_count(client):
    eid = _bootstrap_event(client)
    p1 = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    client.post(f"/api/v1/events/{eid}/photos", files=_files())
    client.patch(
        f"/api/v1/events/{eid}/photos/{p1['id']}",
        json={"is_group_photo": True},
    )

    event = client.get(f"/api/v1/events/{eid}").json()
    assert event["photo_count"] == 2
    assert event["group_photo_url"] == p1["url"]


def test_caption_round_trip(client):
    eid = _bootstrap_event(client)
    p = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    r = client.patch(
        f"/api/v1/events/{eid}/photos/{p['id']}",
        json={"caption": "  Solnedgang fra terrassen  "},
    )
    assert r.status_code == 200
    assert r.json()["caption"] == "Solnedgang fra terrassen"
    # Empty string clears the caption.
    r2 = client.patch(
        f"/api/v1/events/{eid}/photos/{p['id']}", json={"caption": ""}
    )
    assert r2.json()["caption"] is None


def test_uploader_can_delete_own_photo(client):
    eid = _bootstrap_event(client)
    p = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    r = client.delete(f"/api/v1/events/{eid}/photos/{p['id']}")
    assert r.status_code == 204
    assert client.get(f"/api/v1/events/{eid}/photos").json() == []


def test_other_parent_cannot_delete_someone_elses_photo(client):
    """Random parent (not host, not admin, not uploader) gets 403."""
    eid = _bootstrap_event(client)
    p = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    client.post("/api/v1/auth/logout")
    _bootstrap_parent_in_family(client, email="other@example.com")
    r = client.delete(f"/api/v1/events/{eid}/photos/{p['id']}")
    assert r.status_code == 403


def test_admin_can_delete_any_photo(client):
    eid = _bootstrap_event(client)
    # Have a parent upload, then admin deletes.
    client.post("/api/v1/auth/logout")
    _bootstrap_parent_in_family(client, email="uploader@example.com")
    p = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.delete(f"/api/v1/events/{eid}/photos/{p['id']}")
    assert r.status_code == 204


def test_event_host_can_edit_any_photo(client):
    """Promote a parent to host; they should be able to mark any photo as group photo."""
    _bootstrap_parent_in_family(client, email="host@example.com")
    host_id = client.get("/api/v1/auth/me").json()["id"]
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    eid = client.post(
        "/api/v1/events",
        json={
            "name": "Hosted",
            "start_date": "2026-07-10",
            "end_date": "2026-07-11",
            "host_user_id": host_id,
        },
    ).json()["id"]
    # Admin uploads a photo.
    p = client.post(f"/api/v1/events/{eid}/photos", files=_files()).json()[0]
    client.post("/api/v1/auth/logout")
    _login(client, "host@example.com", "password123")
    r = client.patch(
        f"/api/v1/events/{eid}/photos/{p['id']}",
        json={"is_group_photo": True},
    )
    assert r.status_code == 200
    assert r.json()["is_group_photo"] is True


def test_upload_rejects_non_image(client):
    eid = _bootstrap_event(client)
    r = client.post(
        f"/api/v1/events/{eid}/photos",
        files=[("files", ("dummy.png", io.BytesIO(b"not an image"), "image/png"))],
    )
    assert r.status_code == 400, r.text


def test_upload_rejects_bad_extension(client):
    eid = _bootstrap_event(client)
    r = client.post(
        f"/api/v1/events/{eid}/photos",
        files=[("files", ("vibes.txt", io.BytesIO(b"hi"), "text/plain"))],
    )
    assert r.status_code == 400


def test_upload_missing_event_404(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    r = client.post("/api/v1/events/99999/photos", files=_files())
    assert r.status_code == 404


def test_delete_cascade_when_event_removed(client):
    """Deleting an event cascades photos so they don't dangle."""
    eid = _bootstrap_event(client)
    client.post(f"/api/v1/events/{eid}/photos", files=_files())
    assert client.delete(f"/api/v1/events/{eid}").status_code == 204
    # Gallery shouldn't list the orphan.
    g = client.get("/api/v1/events/photos/gallery").json()
    assert all(p["event_id"] != eid for p in g)


def test_gallery_orders_by_event_date_desc(client):
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    e_old = client.post(
        "/api/v1/events",
        json={"name": "Old", "start_date": "2024-01-01", "end_date": "2024-01-02"},
    ).json()["id"]
    e_new = client.post(
        "/api/v1/events",
        json={"name": "New", "start_date": "2026-07-10", "end_date": "2026-07-11"},
    ).json()["id"]
    client.post(f"/api/v1/events/{e_old}/photos", files=_files("old.png"))
    client.post(f"/api/v1/events/{e_new}/photos", files=_files("new.png"))

    g = client.get("/api/v1/events/photos/gallery").json()
    # Newer event's photos come first.
    new_idx = next(i for i, p in enumerate(g) if p["event_id"] == e_new)
    old_idx = next(i for i, p in enumerate(g) if p["event_id"] == e_old)
    assert new_idx < old_idx


def test_gallery_pagination(client):
    eid = _bootstrap_event(client)
    client.post(f"/api/v1/events/{eid}/photos", files=_files_multi(5))
    g1 = client.get("/api/v1/events/photos/gallery?limit=2").json()
    g2 = client.get("/api/v1/events/photos/gallery?limit=2&offset=2").json()
    assert len(g1) == 2
    assert len(g2) == 2
    assert {p["id"] for p in g1}.isdisjoint({p["id"] for p in g2})


def test_listing_photos_includes_uploader(client):
    """Frontend needs uploader_user_id to decide whether to show edit/delete controls."""
    _bootstrap_parent_in_family(client, email="up@example.com")
    me = client.get("/api/v1/auth/me").json()
    client.post("/api/v1/auth/logout")
    _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)
    eid = client.post(
        "/api/v1/events",
        json={"name": "P", "start_date": str(date.today()), "end_date": str(date.today())},
    ).json()["id"]
    client.post("/api/v1/auth/logout")
    _login(client, "up@example.com", "password123")
    client.post(f"/api/v1/events/{eid}/photos", files=_files())

    listing = client.get(f"/api/v1/events/{eid}/photos").json()
    assert listing[0]["uploader_user_id"] == me["id"]
