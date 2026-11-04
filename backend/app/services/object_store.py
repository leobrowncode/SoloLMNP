"""Documents and dossier archives: local disk, or private Vercel Blob.

The choice is ``BLOB_READ_WRITE_TOKEN``. Empty means the disk directories used
by development and tests. A token means every byte goes to a private Blob
store. Callers use a key (``documents/<generated>`` or ``dossier-exports/<file>``)
and never a URL.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.core.config import Settings
from app.domain.documents.keys import UnsafeObjectKey, split_key
from app.services.blob_api import BlobApiError, BlobNotFound, BlobTransport, VercelBlobClient


class ObjectMissing(FileNotFoundError):
    """No object for this key."""


class ObjectStoreError(RuntimeError):
    """The store refused the operation."""


class ObjectStore(Protocol):
    def put(
        self,
        key: str,
        content: bytes,
        content_type: str,
        *,
        overwrite: bool = False,
    ) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def list_names(self, namespace: str) -> list[str]: ...


class LocalDiskStore:
    """``documents`` stays the existing directory. Archives sit beside it."""

    def __init__(self, documents_dir: Path, exports_dir: Path) -> None:
        self._roots = {"documents": documents_dir, "dossier-exports": exports_dir}

    def put(self, key: str, content: bytes, content_type: str, *, overwrite: bool = False) -> None:
        del content_type
        target = self._path(key)
        if target.is_symlink():
            raise ObjectStoreError("Lien de stockage refusé.")
        if target.exists() and not overwrite:
            raise ObjectStoreError("Objet déjà présent.")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.partial")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, key: str) -> bytes:
        target = self._path(key)
        if target.is_symlink() or not target.is_file():
            raise ObjectMissing(key)
        return target.read_bytes()

    def delete(self, key: str) -> None:
        target = self._path(key)
        if target.is_symlink():
            raise ObjectStoreError("Lien de stockage refusé.")
        target.unlink(missing_ok=True)

    def list_names(self, namespace: str) -> list[str]:
        root = self._root(namespace)
        if not root.is_dir():
            return []
        names: list[str] = []
        for path in root.iterdir():
            if path.is_symlink() or not path.is_file():
                continue
            try:
                split_key(f"{namespace}/{path.name}")
            except UnsafeObjectKey:
                continue
            names.append(path.name)
        return sorted(names)

    def _root(self, namespace: str) -> Path:
        try:
            return self._roots[namespace]
        except KeyError as exc:
            raise ObjectStoreError("Espace de stockage refusé.") from exc

    def _path(self, key: str) -> Path:
        try:
            namespace, name = split_key(key)
        except UnsafeObjectKey as exc:
            raise ObjectStoreError("Clé de stockage refusée.") from exc
        root = self._root(namespace)
        target = root / name
        if target.parent != root:
            raise ObjectStoreError("Clé de stockage refusée.")
        return target


class VercelBlobStore:
    def __init__(self, token: str, transport: BlobTransport | None = None) -> None:
        self._client = VercelBlobClient(token, transport)

    def put(self, key: str, content: bytes, content_type: str, *, overwrite: bool = False) -> None:
        _require_key(key)
        try:
            self._client.put(key, content, content_type, overwrite=overwrite)
        except BlobApiError as exc:
            raise ObjectStoreError(str(exc)) from exc

    def get(self, key: str) -> bytes:
        _require_key(key)
        try:
            return self._client.get(key)
        except BlobNotFound as exc:
            raise ObjectMissing(key) from exc
        except BlobApiError as exc:
            raise ObjectStoreError(str(exc)) from exc

    def delete(self, key: str) -> None:
        _require_key(key)
        try:
            self._client.delete(key)
        except BlobApiError as exc:
            raise ObjectStoreError(str(exc)) from exc

    def list_names(self, namespace: str) -> list[str]:
        if namespace not in {"documents", "dossier-exports"}:
            raise ObjectStoreError("Espace de stockage refusé.")
        prefix = f"{namespace}/"
        try:
            pathnames = self._client.list_pathnames(prefix)
        except BlobApiError as exc:
            raise ObjectStoreError(str(exc)) from exc
        names: list[str] = []
        for pathname in pathnames:
            if not pathname.startswith(prefix):
                continue
            name = pathname.removeprefix(prefix)
            try:
                split_key(f"{namespace}/{name}")
            except UnsafeObjectKey:
                continue
            names.append(name)
        return sorted(names)


def _require_key(key: str) -> None:
    try:
        split_key(key)
    except UnsafeObjectKey as exc:
        raise ObjectStoreError("Clé de stockage refusée.") from exc


def open_store(settings: Settings, transport: BlobTransport | None = None) -> ObjectStore:
    if settings.uses_blob:
        return VercelBlobStore(settings.blob_read_write_token, transport)
    return LocalDiskStore(
        settings.documents_dir,
        settings.documents_dir.parent / "dossier-exports",
    )
