"""Document routes with a private Blob store. The transport never opens a socket."""

import base64
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient

from alembic import command
from app.core.auth import TEST_EMAIL, TEST_SECRET
from app.core.config import Settings
from app.core.database import Database
from app.main import create_app
from app.services.blob_api import BlobResponse

TOKEN = "vercel_blob_rw_12345fakeStoreId_30FakeRandomCharacters12345678"  # noqa: S105
PDF = b"%PDF-1.4 direct"


class MemoryTransport:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> BlobResponse:
        del headers
        if method == "PUT":
            pathname = parse_qs(urlsplit(url).query)["pathname"][0]
            self.objects[pathname] = body or b""
            payload = {
                "pathname": pathname,
                "url": f"https://12345fakeStoreId.private.blob.vercel-storage.com/{pathname}",
            }
            return BlobResponse(200, json.dumps(payload).encode())
        if method == "GET" and ".private.blob.vercel-storage.com" in url:
            pathname = urlsplit(url).path.lstrip("/")
            if pathname not in self.objects:
                return BlobResponse(404, b"missing")
            return BlobResponse(200, self.objects[pathname])
        if method == "POST" and url.endswith("/delete"):
            for name in json.loads(body or b"{}")["urls"]:
                self.objects.pop(str(name), None)
            return BlobResponse(200, b"{}")
        if method == "GET" and "prefix=" in url:
            prefix = parse_qs(urlsplit(url).query)["prefix"][0]
            blobs = [{"pathname": key} for key in sorted(self.objects) if key.startswith(prefix)]
            return BlobResponse(200, json.dumps({"blobs": blobs, "hasMore": False}).encode())
        return BlobResponse(500, b"unexpected")


@pytest.fixture
def blob_api(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.domain.documents.files.INLINE_UPLOAD_BYTES", 8)
    transport = MemoryTransport()
    monkeypatch.setattr("app.services.blob_api.blob_transport", lambda: transport)
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'blob.sqlite3').as_posix()}",
        documents_dir=tmp_path / "documents",
        allowed_hosts=("testserver", "localhost", "127.0.0.1"),
        blob_read_write_token=TOKEN,
        auth_mode="test",
        auth_test_secret=TEST_SECRET,
        allowed_emails=(TEST_EMAIL,),
    )
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.attributes["settings"] = settings
    command.upgrade(config, "head")
    database = Database(settings)
    try:
        with TestClient(create_app(settings), headers={"X-SoloLMNP-Request": "1"}) as api:
            yield api, transport
    finally:
        database.engine.dispose()


def test_inline_upload_download_delete_and_direct_grant(blob_api) -> None:
    api, transport = blob_api
    policy = api.get("/api/filing/storage").json()
    assert policy["backend"] == "blob"
    assert policy["direct_upload"] is True
    assert policy["inline_upload_bytes"] == 8
    assert TOKEN not in json.dumps(policy)

    small = b"%PDF-1"
    assert len(small) <= 8
    stored = api.post(
        "/api/filing/documents",
        json={
            "filename": "petit.pdf",
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(small).decode(),
        },
    )
    assert stored.status_code == 201, stored.text
    assert "http" not in api.get("/api/filing/documents").text
    document_id = stored.json()["id"]
    assert api.get(f"/api/filing/documents/{document_id}/content").content == small
    removed = api.delete(f"/api/filing/documents/{document_id}")
    assert removed.json()["deleted"] is True
    assert transport.objects == {}

    refused = api.post(
        "/api/filing/documents",
        json={
            "filename": "gros.pdf",
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(PDF).decode(),
        },
    )
    assert refused.status_code == 413
    assert refused.json()["detail"]["code"] == "DOCUMENT_BODY_LIMIT"

    grant = api.post(
        "/api/filing/documents/upload-grant",
        json={"filename": "gros.pdf", "media_type": "application/pdf", "size": len(PDF)},
    )
    assert grant.status_code == 200, grant.text
    issued = grant.json()
    assert issued["mode"] == "direct"
    assert TOKEN not in json.dumps(issued)
    assert issued["headers"]["authorization"].startswith("Bearer vercel_blob_client_")
    sent = transport.request("PUT", issued["upload_url"], issued["headers"], PDF)
    assert sent.status == 200
    digest = hashlib.sha256(PDF).hexdigest()
    completed = api.post(
        "/api/filing/documents/complete",
        json={
            "filename": "gros.pdf",
            "media_type": "application/pdf",
            "stored_name": issued["stored_name"],
            "sha256": digest,
            "size": len(PDF),
        },
    )
    assert completed.status_code == 201, completed.text
    assert api.get(f"/api/filing/documents/{completed.json()['id']}/content").content == PDF

    missing = api.post(
        "/api/filing/documents/complete",
        json={
            "filename": "absent.pdf",
            "media_type": "application/pdf",
            "stored_name": "ab" * 16 + ".pdf",
            "sha256": digest,
            "size": len(PDF),
        },
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "UPLOAD_INCOMPLETE"
