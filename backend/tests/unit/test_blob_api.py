"""Vercel Blob client against a fake transport. No socket is opened."""

import base64
import hashlib
import hmac
import json
from collections.abc import Mapping
from urllib.parse import parse_qs, urlsplit

import pytest

from app.domain.documents.files import inline_budget, needs_direct_upload
from app.services.blob_api import (
    BlobApiError,
    BlobResponse,
    UrllibBlobTransport,
    VercelBlobClient,
    issue_client_token,
)
from app.services.object_store import VercelBlobStore

TOKEN = "vercel_blob_rw_12345fakeStoreId_30FakeRandomCharacters12345678"  # noqa: S105
PATH = "documents/abc123.pdf"


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
            pathname = _query(url, "pathname")
            self.objects[pathname] = body or b""
            payload = {
                "pathname": pathname,
                "url": f"https://12345fakeStoreId.private.blob.vercel-storage.com/{pathname}",
            }
            return BlobResponse(200, json.dumps(payload).encode())
        if method == "GET" and ".private.blob.vercel-storage.com" in url:
            pathname = url.split("://", 1)[1].split("/", 1)[1].split("?", 1)[0]
            if pathname not in self.objects:
                return BlobResponse(404, b"missing")
            return BlobResponse(200, self.objects[pathname])
        if method == "POST" and url.endswith("/delete"):
            for name in json.loads(body or b"{}")["urls"]:
                self.objects.pop(name, None)
            return BlobResponse(200, b"{}")
        if method == "GET" and "prefix=" in url:
            prefix = _query(url, "prefix")
            blobs = [{"pathname": key} for key in sorted(self.objects) if key.startswith(prefix)]
            return BlobResponse(200, json.dumps({"blobs": blobs, "hasMore": False}).encode())
        return BlobResponse(500, b"unexpected")


def _query(url: str, key: str) -> str:
    return parse_qs(urlsplit(url).query)[key][0]


def test_inline_budget_stays_under_the_function_body() -> None:
    assert inline_budget(10_000_000, blob=False) == 10_000_000
    assert inline_budget(10_000_000, blob=True) == 3_000_000
    assert needs_direct_upload(3_000_001, 10_000_000, blob=True)
    assert not needs_direct_upload(3_000_000, 10_000_000, blob=True)
    assert not needs_direct_upload(3_000_001, 10_000_000, blob=False)


def test_client_token_is_an_hmac_and_hides_the_read_write_token() -> None:
    issued = issue_client_token(
        TOKEN,
        pathname=PATH,
        content_type="application/pdf",
        maximum_size=12,
        valid_until_ms=1_700_000_000_000,
    )
    assert TOKEN not in issued
    assert issued.startswith("vercel_blob_client_12345fakeStoreId_")
    packed = issued.removeprefix("vercel_blob_client_12345fakeStoreId_")
    signature, encoded = base64.b64decode(packed).decode().split(".", 1)
    expected = hmac.new(TOKEN.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    assert signature == expected
    payload = json.loads(base64.b64decode(encoded))
    assert payload == {
        "pathname": PATH,
        "maximumSizeInBytes": 12,
        "allowedContentTypes": ["application/pdf"],
        "addRandomSuffix": False,
        "allowOverwrite": False,
        "validUntil": 1_700_000_000_000,
    }


def test_store_roundtrip_and_public_url_rejected() -> None:
    transport = MemoryTransport()
    store = VercelBlobStore(TOKEN, transport)
    store.put(PATH, b"%PDF-1.4", "application/pdf")
    assert store.get(PATH) == b"%PDF-1.4"
    assert store.list_names("documents") == ["abc123.pdf"]
    store.delete(PATH)
    assert store.list_names("documents") == []

    class Public:
        def request(
            self,
            method: str,
            url: str,
            headers: Mapping[str, str],
            body: bytes | None,
        ) -> BlobResponse:
            del method, url, headers, body
            payload = {
                "pathname": PATH,
                "url": "https://x.public.blob.vercel-storage.com/" + PATH,
            }
            return BlobResponse(200, json.dumps(payload).encode())

    with pytest.raises(BlobApiError, match="publique"):
        VercelBlobClient(TOKEN, Public()).put(PATH, b"%PDF-", "application/pdf", overwrite=False)


def test_urllib_transport_refuses_hosts_outside_the_blob_api() -> None:
    transport = UrllibBlobTransport()
    with pytest.raises(BlobApiError, match="refusée"):
        transport.request("GET", "https://evil.example/api/blob", {}, None)
    with pytest.raises(BlobApiError, match="refusée"):
        transport.request("GET", "http://vercel.com/api/blob", {}, None)
    with pytest.raises(BlobApiError):
        issue_client_token(
            "not-a-token",
            pathname=PATH,
            content_type="application/pdf",
            maximum_size=1,
            valid_until_ms=1,
        )
