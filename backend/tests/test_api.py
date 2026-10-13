import io
import sys

import pytest


def post(client, headers, data=None, name="a.png", ctype="image/png", body=b"\x89PNGdata", caption="hello"):
    form = {"caption": caption}
    if data is None:
        form["photo"] = (io.BytesIO(body), name, ctype)
    else:
        form.update(data)
    return client.post("/api/photos", headers=headers, data=form)


def test_health_and_info(client):
    assert client.get("/api/health").json == {"status": "ok"}
    assert client.get("/api/info").json == {"instanceId": "local", "zone": "local"}


def test_upload_list_and_image_roundtrip(client, auth):
    r = post(client, auth, caption="  Sunset  ")
    assert r.status_code == 201
    photo = r.json
    assert photo["caption"] == "Sunset"
    assert photo["imageUrl"] == f"/api/photos/{photo['id']}/image"

    listed = client.get("/api/photos").json["photos"]
    assert [p["id"] for p in listed] == [photo["id"]]

    img = client.get(photo["imageUrl"])
    assert img.status_code == 200
    assert img.data == b"\x89PNGdata"
    assert img.content_type == "image/png"
    assert img.headers["X-Content-Type-Options"] == "nosniff"
    assert img.headers["Cache-Control"] == "public, max-age=86400"


def test_newest_photo_listed_first(client, auth):
    first = post(client, auth, caption="one").json["id"]
    second = post(client, auth, caption="two").json["id"]
    ids = [p["id"] for p in client.get("/api/photos").json["photos"]]
    assert ids == [second, first]


def test_unicode_and_html_captions_roundtrip(client, auth):
    for caption in ("café 🎉", "<script>alert(1)</script>"):
        post(client, auth, caption=caption)
    captions = {p["caption"] for p in client.get("/api/photos").json["photos"]}
    assert captions == {"café 🎉", "<script>alert(1)</script>"}


def test_jpeg_extension_stored_as_jpg(client, auth):
    r = post(client, auth, name="x.JPEG", ctype="image/jpeg")
    assert r.status_code == 201
    assert client.get(r.json["imageUrl"]).content_type == "image/jpeg"


@pytest.mark.parametrize("headers", [{}, {"X-Upload-Password": "wrong"}])
def test_wrong_or_missing_password_is_401(client, headers):
    r = post(client, headers)
    assert r.status_code == 401
    assert r.json == {"error": "Wrong upload password"}


def test_password_checked_before_size(client):
    big = b"0" * (6 * 1024 * 1024)
    assert post(client, {"X-Upload-Password": "wrong"}, body=big).status_code == 401


def test_too_large_is_413_json(client, auth):
    r = post(client, auth, body=b"0" * (6 * 1024 * 1024))
    assert r.status_code == 413
    assert r.json == {"error": "That file is too big (5 MB maximum)"}


def test_missing_fields_is_400(client, auth):
    assert client.post("/api/photos", headers=auth, data={"caption": "x"}).status_code == 400
    r = client.post("/api/photos", headers=auth, data={"photo": (io.BytesIO(b"x"), "a.png", "image/png")})
    assert r.status_code == 400


@pytest.mark.parametrize("name,ctype", [
    ("a.txt", "text/plain"),
    ("a.png", "text/plain"),      # extension ok, type wrong
    ("a.txt", "image/png"),       # type ok, extension wrong
    ("a.jpg", "image/png"),       # mismatched pair
    ("noext", "image/png"),
])
def test_disallowed_type_is_400(client, auth, name, ctype):
    r = post(client, auth, name=name, ctype=ctype)
    assert r.status_code == 400
    assert r.json == {"error": "Only JPEG, PNG, GIF or WebP images are allowed"}


@pytest.mark.parametrize("caption", ["", "   ", "x" * 201, "🎉" * 200])
def test_bad_caption_is_400(client, auth, caption):
    r = post(client, auth, caption=caption)
    assert r.status_code == 400
    assert r.json == {"error": "Caption must be 1 to 200 characters"}


def test_caption_200_chars_accepted(client, auth):
    assert post(client, auth, caption="x" * 200).status_code == 201


@pytest.mark.parametrize("photo_id", [
    "..", "abc", "1234567890123-DEADBEEF", "1234567890123-deadbee", "12345678901234-deadbeef",
    "1234567890123-deadbeef/../x",
])
def test_malformed_image_id_is_404(client, photo_id):
    r = client.get(f"/api/photos/{photo_id}/image")
    assert r.status_code == 404


def test_unknown_image_id_is_404_json(client):
    r = client.get("/api/photos/1234567890123-deadbeef/image")
    assert r.status_code == 404
    assert "error" in r.json


def test_framework_errors_are_json(client):
    assert "error" in client.get("/api/nope").json
    r = client.put("/api/photos")
    assert r.status_code == 405 and "error" in r.json


def test_uploads_503_when_password_not_loaded(client, auth):
    sys.modules["config"].UPLOAD_PASSWORD = None
    r = post(client, auth)
    assert r.status_code == 503
    assert r.json == {"error": "Uploads are temporarily unavailable"}
    # Viewing still works.
    assert client.get("/api/photos").status_code == 200


def test_listing_skips_objects_with_unreadable_metadata(client, auth):
    import boto3
    post(client, auth, caption="good")
    boto3.client("s3", region_name="us-east-1").put_object(
        Bucket="photo-test-bucket", Key="photos/0000000000000-aaaaaaaa.png", Body=b"x")
    photos = client.get("/api/photos").json["photos"]
    assert [p["caption"] for p in photos] == ["good"]
