"""PDF minimal, Helvetica WinAnsi. Pas de bibliothèque ajoutée."""

from __future__ import annotations


def pdf_texte(title: str, lines: list[str]) -> bytes:
    pages = _pages([_latin(title), ""] + [_latin(line) for line in lines])
    return _document(pages)


def _pages(lines: list[str]) -> list[str]:
    size = 46
    chunks = [lines[index : index + size] for index in range(0, len(lines), size)] or [[]]
    streams: list[str] = []
    for chunk in chunks:
        body = ["BT", "/F1 9 Tf", "40 800 Td", "14 TL"]
        for line in chunk:
            body.append(f"({_escape(line[:110])}) Tj T*")
        body.append("ET")
        streams.append("\n".join(body))
    return streams


def _document(streams: list[str]) -> bytes:
    objects: list[bytes] = []
    page_ids = list(range(3, 3 + len(streams)))
    font_id = 3 + len(streams)
    content_ids = list(range(font_id + 1, font_id + 1 + len(streams)))
    kids = " ".join(f"{page} 0 R" for page in page_ids)
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(streams)} >>".encode())
    for _page, content in zip(page_ids, content_ids, strict=True):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Contents {content} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode()
        )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    for stream in streams:
        raw = stream.encode("latin-1")
        header = b"<< /Length " + str(len(raw)).encode() + b" >>\nstream\n"
        objects.append(header + raw + b"\nendstream")
    return _assemble(objects)


def _assemble(objects: list[bytes]) -> bytes:
    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    parts = [header]
    offsets = [0]
    cursor = len(header)
    for index, body in enumerate(objects, start=1):
        chunk = f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
        offsets.append(cursor)
        parts.append(chunk)
        cursor += len(chunk)
    xref_at = cursor
    xref = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    xref.extend(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
    trailer = (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    )
    return b"".join(parts) + "".join(xref).encode() + trailer.encode()


def _latin(value: str) -> str:
    cleaned = (
        value.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("œ", "oe")
        .replace("Œ", "OE")
        .replace("’", "'")
    )
    return cleaned.encode("latin-1", "replace").decode("latin-1")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
