"""Dépôt du dossier v1 : fichiers locaux, ou Blob privé via un client injecté.

Le calcul n'est pas ici. Chaque compte a un préfixe. Un chemin relatif ne sort pas de ce préfixe.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4

_OWNER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DepotError(ValueError):
    """Chemin ou clé refusés."""


class DepotAbsent(FileNotFoundError):
    """Pas d'objet pour ce compte et ce chemin."""


class ClientBlob(Protocol):
    def put(
        self, pathname: str, content: bytes, content_type: str, *, overwrite: bool
    ) -> None: ...

    def get(self, pathname: str) -> bytes: ...

    def list_pathnames(self, prefix: str) -> list[str]: ...


class Depot(Protocol):
    def lire(self, owner: str, relatif: str) -> bytes: ...

    def ecrire(self, owner: str, relatif: str, contenu: bytes) -> None: ...

    def existe(self, owner: str, relatif: str) -> bool: ...

    def lister(self, owner: str, prefixe: str = "") -> list[str]: ...

    def retirer(self, owner: str, relatif: str) -> None: ...


def cle_owner(subject: str) -> str:
    """Identifiant de dossier stable. Un sujet unsafe est ramené à une empreinte."""
    if _OWNER.fullmatch(subject):
        return subject
    return "u-" + hashlib.sha256(subject.encode()).hexdigest()[:32]


def relatif_sur(relatif: str) -> str:
    if not relatif or relatif.startswith(("/", "\\")) or "\\" in relatif:
        raise DepotError("Chemin refusé.")
    parts = relatif.split("/")
    if len(parts) > 4 or any(not _SEGMENT.fullmatch(part) for part in parts):
        raise DepotError("Chemin refusé.")
    return "/".join(parts)


def type_mime(nom: str) -> str:
    bas = nom.lower()
    if bas.endswith(".pdf"):
        return "application/pdf"
    if bas.endswith(".csv"):
        return "text/csv; charset=utf-8"
    if bas.endswith((".yaml", ".yml")):
        return "text/yaml; charset=utf-8"
    if bas.endswith(".txt"):
        return "text/plain; charset=utf-8"
    if bas.endswith(".json"):
        return "application/json"
    if bas.endswith(".zip"):
        return "application/zip"
    if bas.endswith(".png"):
        return "image/png"
    if bas.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if bas.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


class DepotFichiers:
    """Arborescence `racine/<owner>/`. Le layout YAML + CSV ne change pas, le préfixe isole."""

    def __init__(self, racine: Path) -> None:
        self._racine = racine

    def lire(self, owner: str, relatif: str) -> bytes:
        cible = self._cible(owner, relatif)
        if cible.is_symlink() or not cible.is_file():
            raise DepotAbsent(relatif)
        return cible.read_bytes()

    def ecrire(self, owner: str, relatif: str, contenu: bytes) -> None:
        cible = self._cible(owner, relatif)
        if cible.is_symlink():
            raise DepotError("Lien refusé.")
        cible.parent.mkdir(parents=True, exist_ok=True)
        temporaire = cible.with_name(f".{cible.name}.{uuid4().hex}.partial")
        try:
            temporaire.write_bytes(contenu)
            os.replace(temporaire, cible)
        finally:
            temporaire.unlink(missing_ok=True)

    def existe(self, owner: str, relatif: str) -> bool:
        try:
            cible = self._cible(owner, relatif)
        except DepotError:
            return False
        return cible.is_file() and not cible.is_symlink()

    def lister(self, owner: str, prefixe: str = "") -> list[str]:
        try:
            dossier = self._dossier(owner)
        except DepotError:
            return []
        if not dossier.is_dir():
            return []
        base = dossier
        if prefixe:
            base = self._cible(owner, prefixe)
            if base.is_file() and not base.is_symlink():
                return [relatif_sur(prefixe)]
            if not base.is_dir() or base.is_symlink():
                return []
        noms: list[str] = []
        for chemin in base.rglob("*"):
            if chemin.is_symlink() or not chemin.is_file():
                continue
            rel = chemin.relative_to(dossier).as_posix()
            try:
                relatif_sur(rel)
            except DepotError:
                continue
            noms.append(rel)
        return sorted(noms)

    def retirer(self, owner: str, relatif: str) -> None:
        cible = self._cible(owner, relatif)
        if cible.is_symlink():
            raise DepotError("Lien refusé.")
        cible.unlink(missing_ok=True)

    def _dossier(self, owner: str) -> Path:
        cle = cle_owner(owner)
        dossier = self._racine / cle
        if dossier.is_symlink():
            raise DepotError("Lien refusé.")
        racine = self._racine.resolve()
        resolu = dossier.resolve()
        if resolu != racine and racine not in resolu.parents:
            raise DepotError("Chemin refusé.")
        return resolu

    def _cible(self, owner: str, relatif: str) -> Path:
        rel = relatif_sur(relatif)
        dossier = self._dossier(owner)
        cible = (dossier / rel).resolve()
        if cible != dossier and dossier not in cible.parents:
            raise DepotError("Chemin refusé.")
        return cible


class AdaptateurBlob:
    """Le client Blob lève sa propre absence. Le dépôt attend FileNotFoundError."""

    def __init__(
        self,
        client: ClientBlob,
        absent: tuple[type[BaseException], ...] = (FileNotFoundError,),
    ) -> None:
        self._client = client
        self._absent = absent

    def put(self, pathname: str, content: bytes, content_type: str, *, overwrite: bool) -> None:
        self._client.put(pathname, content, content_type, overwrite=overwrite)

    def get(self, pathname: str) -> bytes:
        try:
            return self._client.get(pathname)
        except self._absent as exc:
            raise FileNotFoundError(pathname) from exc

    def list_pathnames(self, prefix: str) -> list[str]:
        return self._client.list_pathnames(prefix)


class DepotBlob:
    """Clés `v1/<owner>/<chemin>`. Le client est celui déjà en place, ou un faux en test."""

    def __init__(self, client: ClientBlob, prefixe: str = "v1") -> None:
        if not _SEGMENT.fullmatch(prefixe):
            raise DepotError("Préfixe refusé.")
        self._client = client
        self._prefixe = prefixe

    def lire(self, owner: str, relatif: str) -> bytes:
        try:
            return self._client.get(self._clef(owner, relatif))
        except FileNotFoundError as exc:
            raise DepotAbsent(relatif) from exc

    def ecrire(self, owner: str, relatif: str, contenu: bytes) -> None:
        self._client.put(
            self._clef(owner, relatif),
            contenu,
            type_mime(relatif),
            overwrite=True,
        )

    def existe(self, owner: str, relatif: str) -> bool:
        try:
            self.lire(owner, relatif)
        except DepotAbsent:
            return False
        return True

    def lister(self, owner: str, prefixe: str = "") -> list[str]:
        garde = ""
        if prefixe:
            garde = relatif_sur(prefixe.rstrip("/"))
        racine = f"{self._prefixe}/{cle_owner(owner)}/"
        noms: list[str] = []
        for pathname in self._client.list_pathnames(racine):
            if not pathname.startswith(racine):
                continue
            rel = pathname.removeprefix(racine)
            try:
                relatif_sur(rel)
            except DepotError:
                continue
            if garde and rel != garde and not rel.startswith(garde + "/"):
                continue
            noms.append(rel)
        return sorted(noms)

    def retirer(self, owner: str, relatif: str) -> None:
        client = self._client
        effacer = getattr(client, "delete", None)
        if not callable(effacer):
            raise DepotError("Ce dépôt ne retire pas.")
        try:
            effacer(self._clef(owner, relatif))
        except FileNotFoundError:
            return

    def _clef(self, owner: str, relatif: str) -> str:
        return f"{self._prefixe}/{cle_owner(owner)}/{relatif_sur(relatif)}"
