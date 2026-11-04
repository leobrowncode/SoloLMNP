"""Object keys are a namespace plus one generated file name. Never a user path."""

from pathlib import Path

NAMESPACES = frozenset({"documents", "dossier-exports"})


class UnsafeObjectKey(ValueError):
    """The key is not a single safe file name under an allowed namespace."""


def safe_segment(name: str) -> bool:
    if (
        not name
        or name.startswith(".")
        or name in {".", ".."}
        or "\x00" in name
        or ".." in name
        or "\\" in name
        or "/" in name
        or name != Path(name).name
    ):
        return False
    return True


def split_key(key: str) -> tuple[str, str]:
    if key.count("/") != 1:
        raise UnsafeObjectKey("Clé de stockage refusée.")
    namespace, name = key.split("/", 1)
    if namespace not in NAMESPACES or not safe_segment(name):
        raise UnsafeObjectKey("Clé de stockage refusée.")
    return namespace, name


def document_key(stored_name: str) -> str:
    if not safe_segment(stored_name):
        raise UnsafeObjectKey("Clé de stockage refusée.")
    return f"documents/{stored_name}"


def export_key(filename: str) -> str:
    if not safe_segment(filename):
        raise UnsafeObjectKey("Clé de stockage refusée.")
    return f"dossier-exports/{filename}"
