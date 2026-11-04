"""File types accepted for a supporting document. The bytes must match the type."""

EXTENSIONS = {"application/pdf": "pdf", "image/jpeg": "jpg", "image/png": "png"}
SIGNATURES = {
    "application/pdf": (b"%PDF-",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}

# Vercel refuses a function body above 4.5 MiB. Base64 expands by 4/3, so an
# inline upload stays at 3 MiB and anything larger goes straight to Blob.
VERCEL_FUNCTION_BODY_BYTES = 4_500_000
INLINE_UPLOAD_BYTES = 3_000_000


def matches_signature(media_type: str, content: bytes) -> bool:
    signatures = SIGNATURES.get(media_type)
    if not content or signatures is None:
        return False
    return content.startswith(signatures)


def extension_for(media_type: str) -> str:
    try:
        return EXTENSIONS[media_type]
    except KeyError as exc:
        raise ValueError("Type de justificatif refusé.") from exc


def inline_budget(max_upload_bytes: int, *, blob: bool) -> int:
    if not blob:
        return max_upload_bytes
    return min(max_upload_bytes, INLINE_UPLOAD_BYTES)


def needs_direct_upload(size: int, max_upload_bytes: int, *, blob: bool) -> bool:
    return blob and size > inline_budget(max_upload_bytes, blob=True)
