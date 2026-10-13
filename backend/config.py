import logging
import os

import boto3

log = logging.getLogger("photo-wall")

PORT = int(os.environ.get("PORT", "8080"))
BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
UPLOAD_PASSWORD_PARAM = os.environ.get("UPLOAD_PASSWORD_PARAM", "/photo-wall/upload-password")
INSTANCE_ID = os.environ.get("INSTANCE_ID", "local")
ZONE = os.environ.get("ZONE", "local")


def _load_upload_password():
    local = os.environ.get("UPLOAD_PASSWORD")
    if local:
        log.warning("Using UPLOAD_PASSWORD from the environment (local testing only)")
        return local
    try:
        ssm = boto3.client("ssm", region_name=AWS_REGION)
        resp = ssm.get_parameter(Name=UPLOAD_PASSWORD_PARAM, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception:
        log.exception("Could not load upload password from Parameter Store")
        return None


# Loaded once at startup. None means uploads are unavailable.
UPLOAD_PASSWORD = _load_upload_password()
