import logging
import secrets
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import boto3

import config

log = logging.getLogger("photo-wall")

_s3 = boto3.client("s3", region_name=config.AWS_REGION)


def new_id():
    now_ms = int(time.time() * 1000)
    return f"{9999999999999 - now_ms:013d}-{secrets.token_hex(4)}"


def upload_photo(data, content_type, ext, caption):
    photo_id = new_id()
    uploaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    _s3.put_object(
        Bucket=config.BUCKET_NAME,
        Key=f"photos/{photo_id}.{ext}",
        Body=data,
        ContentType=content_type,
        Metadata={"caption": urllib.parse.quote(caption), "uploaded-at": uploaded_at},
    )
    return _photo(photo_id, caption, uploaded_at)


def _photo(photo_id, caption, uploaded_at):
    return {
        "id": photo_id,
        "caption": caption,
        "uploadedAt": uploaded_at,
        "imageUrl": f"/api/photos/{photo_id}/image",
    }


def _head(key):
    try:
        meta = _s3.head_object(Bucket=config.BUCKET_NAME, Key=key)["Metadata"]
        photo_id = key[len("photos/"):].rsplit(".", 1)[0]
        return _photo(photo_id, urllib.parse.unquote(meta["caption"]), meta["uploaded-at"])
    except Exception:
        log.exception("Skipping %s: cannot read metadata", key)
        return None


def list_photos():
    resp = _s3.list_objects_v2(Bucket=config.BUCKET_NAME, Prefix="photos/", MaxKeys=50)
    keys = [o["Key"] for o in resp.get("Contents", [])]
    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(_head, keys))  # map keeps S3's order
    return [p for p in results if p]


def open_image(photo_id):
    """Return (body_stream_chunks, content_type) or None if not found."""
    resp = _s3.list_objects_v2(Bucket=config.BUCKET_NAME, Prefix=f"photos/{photo_id}.", MaxKeys=1)
    contents = resp.get("Contents")
    if not contents:
        return None
    obj = _s3.get_object(Bucket=config.BUCKET_NAME, Key=contents[0]["Key"])
    return obj["Body"].iter_chunks(chunk_size=65536), obj["ContentType"]
