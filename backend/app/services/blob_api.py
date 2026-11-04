"""Small synchronous client for the Vercel Blob HTTP API.

Private blobs only. The read-write token stays on the server. A browser upload
receives a client token signed for one pathname, one media type and one size.
Nothing here is called when ``BLOB_READ_WRITE_TOKEN`` is empty. Tests pass a
fake transport and do not open a socket.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urlsplit

API_URL = "https://vercel.com/api/blob"
API_VERSION = "13"
_STORE = re.compile(r"^[A-Za-z0-9]+$")
_TOKEN_PARTS = 5


class BlobApiError(RuntimeError):
    """The Blob API refused the call. The message never includes the token."""


class BlobNotFound(BlobApiError):
    """No object at this pathname."""


@dataclass(frozen=True)
class BlobResponse:
    status: int
    body: bytes


class BlobTransport(Protocol):
    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> BlobResponse: ...


def store_id_from_token(token: str) -> str:
    parts = token.split("_")
    if (
        len(parts) < _TOKEN_PARTS
        or parts[0] != "vercel"
        or parts[1] != "blob"
        or parts[2] != "rw"
        or _STORE.fullmatch(parts[3]) is None
    ):
        raise BlobApiError("Jeton Blob illisible.")
    return parts[3]


def issue_client_token(
    read_write_token: str,
    *,
    pathname: str,
    content_type: str,
    maximum_size: int,
    valid_until_ms: int,
) -> str:
    """HMAC client token, same shape as the Vercel Blob client-token helper."""
    store_id = store_id_from_token(read_write_token)
    payload = {
        "pathname": pathname,
        "maximumSizeInBytes": maximum_size,
        "allowedContentTypes": [content_type],
        "addRandomSuffix": False,
        "allowOverwrite": False,
        "validUntil": valid_until_ms,
    }
    encoded = base64.b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    ).decode("ascii")
    signature = hmac.new(
        read_write_token.encode(),
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()
    packed = base64.b64encode(f"{signature}.{encoded}".encode()).decode("ascii")
    return f"vercel_blob_client_{store_id}_{packed}"


def put_url(pathname: str) -> str:
    return f"{API_URL}/?pathname={quote(pathname, safe='')}"


def private_read_url(store_id: str, pathname: str) -> str:
    return f"https://{store_id}.private.blob.vercel-storage.com/{quote(pathname, safe='/')}?cache=0"


def _allowed(url: str) -> bool:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https":
        return False
    if host == "vercel.com" and parsed.path.startswith("/api/blob"):
        return True
    return host.endswith(".private.blob.vercel-storage.com")


class UrllibBlobTransport:
    def __init__(self, timeout: float = 120) -> None:
        self.timeout = timeout

    def request(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
    ) -> BlobResponse:
        if not _allowed(url):
            raise BlobApiError("URL Blob refusée.")
        request = urllib.request.Request(  # noqa: S310
            url, data=body, headers=dict(headers), method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310
                return BlobResponse(status=response.status, body=response.read())
        except urllib.error.HTTPError as error:
            payload = error.read()
            return BlobResponse(status=error.code, body=payload)


def blob_transport() -> BlobTransport:
    return UrllibBlobTransport()


def _auth(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}", "x-api-version": API_VERSION}


def _raise_for_status(response: BlobResponse, *, missing: BlobApiError | None = None) -> bytes:
    if response.status == 404 and missing is not None:
        raise missing
    if response.status < 200 or response.status >= 300:
        raise BlobApiError(f"Le stockage objet a répondu {response.status}.")
    return response.body


class VercelBlobClient:
    def __init__(self, token: str, transport: BlobTransport | None = None) -> None:
        self._token = token
        self._store_id = store_id_from_token(token)
        self._transport = transport if transport is not None else blob_transport()

    def put(self, pathname: str, content: bytes, content_type: str, *, overwrite: bool) -> None:
        headers = {
            **_auth(self._token),
            "x-vercel-blob-access": "private",
            "x-content-type": content_type,
            "x-add-random-suffix": "0",
            "x-allow-overwrite": "1" if overwrite else "0",
        }
        response = self._transport.request("PUT", put_url(pathname), headers, content)
        raw = _raise_for_status(response)
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise BlobApiError("Réponse Blob illisible.") from exc
        returned = loaded.get("pathname") if isinstance(loaded, dict) else None
        if returned != pathname:
            raise BlobApiError("Le stockage objet a enregistré un autre chemin.")
        url = loaded.get("url") if isinstance(loaded, dict) else None
        if isinstance(url, str) and ".public.blob.vercel-storage.com" in url:
            raise BlobApiError("Le stockage objet a publié une URL publique.")

    def get(self, pathname: str) -> bytes:
        response = self._transport.request(
            "GET",
            private_read_url(self._store_id, pathname),
            _auth(self._token),
            None,
        )
        return _raise_for_status(response, missing=BlobNotFound("Objet introuvable."))

    def delete(self, pathname: str) -> None:
        body = json.dumps({"urls": [pathname]}, separators=(",", ":")).encode()
        headers = {**_auth(self._token), "content-type": "application/json"}
        response = self._transport.request("POST", f"{API_URL}/delete", headers, body)
        _raise_for_status(response)

    def list_pathnames(self, prefix: str) -> list[str]:
        names: list[str] = []
        cursor: str | None = None
        while True:
            query = f"prefix={quote(prefix, safe='')}"
            if cursor is not None:
                query = f"{query}&cursor={quote(cursor, safe='')}"
            response = self._transport.request(
                "GET", f"{API_URL}?{query}", _auth(self._token), None
            )
            raw = _raise_for_status(response)
            try:
                loaded = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise BlobApiError("Liste Blob illisible.") from exc
            if not isinstance(loaded, dict):
                raise BlobApiError("Liste Blob illisible.")
            blobs = loaded.get("blobs")
            if not isinstance(blobs, list):
                raise BlobApiError("Liste Blob illisible.")
            for item in blobs:
                if not isinstance(item, dict) or not isinstance(item.get("pathname"), str):
                    raise BlobApiError("Liste Blob illisible.")
                names.append(str(item["pathname"]))
            if loaded.get("hasMore") is not True:
                return names
            next_cursor = loaded.get("cursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                raise BlobApiError("Liste Blob illisible.")
            cursor = next_cursor
