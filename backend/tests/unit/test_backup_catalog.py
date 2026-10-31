"""Archive member rules: registered files stay, placeholders are ignored, traversal is refused."""

import pytest

from app.domain.filing.backup_catalog import (
    UnsafeDocumentPath,
    archived_document_names,
    classify_document_member,
)


def test_classify_keeps_a_stored_name_and_ignores_a_placeholder() -> None:
    assert classify_document_member("database.sqlite3") is None
    assert classify_document_member("manifest.json") is None
    assert classify_document_member("documents/") is None
    assert classify_document_member("documents/abc.pdf") == "keep"
    assert classify_document_member("documents/.gitkeep") == "ignore"
    assert classify_document_member("documents/.hidden") == "ignore"


@pytest.mark.parametrize(
    "member",
    [
        "documents/../secret.txt",
        "documents/sous-dossier/secret.pdf",
        "documents/..\\secret.txt",
        "documents/..",
        "documents/.",
        "documents/a/../../etc/passwd",
        "documents/nom\x00.pdf",
    ],
)
def test_classify_refuses_unsafe_document_names(member: str) -> None:
    with pytest.raises(UnsafeDocumentPath):
        classify_document_member(member)


def test_archived_names_drop_hidden_orphans_and_unsafe_registered_names() -> None:
    present = [".gitkeep", "orphelin.pdf", "une.pdf", "deux.pdf", "../secret.pdf"]
    registered = ["une.pdf", ".gitkeep", "../secret.pdf", "absent.pdf"]
    assert archived_document_names(present, registered) == ["une.pdf"]
