import importlib
import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BUCKET = "photo-test-bucket"
PASSWORD = "test-password"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BUCKET_NAME", BUCKET)
    monkeypatch.setenv("UPLOAD_PASSWORD", PASSWORD)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    with mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)
        # Re-import so module-level boto3 clients and config bind to the mock.
        for name in ("config", "storage", "app"):
            sys.modules.pop(name, None)
        app = importlib.import_module("app")
        yield app.app.test_client()


@pytest.fixture
def auth():
    return {"X-Upload-Password": PASSWORD}
