import hmac
import logging
import os
import re
import urllib.parse

logging.basicConfig(level=logging.INFO)

from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import HTTPException

import config
import storage

log = logging.getLogger("photo-wall")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ID_RE = re.compile(r"^\d{13}-[0-9a-f]{8}$")
TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
         "gif": "image/gif", "webp": "image/webp"}


def error(message, status):
    return jsonify({"error": message}), status


@app.errorhandler(413)
def too_large(_e):
    return error("That file is too big (5 MB maximum)", 413)


@app.errorhandler(HTTPException)
def http_error(e):
    return error(e.description or e.name, e.code)


@app.errorhandler(500)
def server_error(_e):
    return error("Something went wrong", 500)


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/info")
def info():
    return jsonify({"instanceId": config.INSTANCE_ID, "zone": config.ZONE})


@app.get("/api/photos")
def list_photos():
    try:
        return jsonify({"photos": storage.list_photos()})
    except Exception:
        log.exception("Listing photos failed")
        return error("Could not load photos", 500)


@app.post("/api/photos")
def upload_photo():
    if config.UPLOAD_PASSWORD is None:
        return error("Uploads are temporarily unavailable", 503)
    supplied = request.headers.get("X-Upload-Password", "")
    if not hmac.compare_digest(supplied.encode(), config.UPLOAD_PASSWORD.encode()):
        return error("Wrong upload password", 401)

    # Accessing request.files/form triggers the 413 handler for oversize bodies.
    photo = request.files.get("photo")
    caption = request.form.get("caption")
    if photo is None or caption is None:
        return error("A photo and a caption are required", 400)

    ext = os.path.splitext(photo.filename or "")[1].lstrip(".").lower()
    ctype = (photo.mimetype or "").lower()
    if ext not in TYPES or TYPES[ext] != ctype:
        return error("Only JPEG, PNG, GIF or WebP images are allowed", 400)

    caption = caption.strip()
    # S3 user metadata is limited to 2 KB; the caption is stored URL-quoted.
    if not 1 <= len(caption) <= 200 or len(urllib.parse.quote(caption)) > 1900:
        return error("Caption must be 1 to 200 characters", 400)

    try:
        result = storage.upload_photo(photo.read(), ctype, "jpg" if ext == "jpeg" else ext, caption)
    except Exception:
        log.exception("Upload failed")
        return error("Upload failed, please try again", 500)
    return jsonify(result), 201


@app.get("/api/photos/<photo_id>/image")
def photo_image(photo_id):
    if not ID_RE.match(photo_id):
        return error("Not found", 404)
    try:
        found = storage.open_image(photo_id)
    except Exception:
        log.exception("Image fetch failed")
        return error("Not found", 404)
    if found is None:
        return error("Not found", 404)
    chunks, ctype = found
    return Response(chunks, content_type=ctype, headers={
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "public, max-age=86400",
    })
