"""Archive reproductible. Chaque fichier a son empreinte SHA-256."""

from __future__ import annotations

import hashlib
import io
import zipfile

_DATE = (2020, 1, 1, 0, 0, 0)


def zipper(files: list[tuple[str, bytes]]) -> tuple[bytes, str, dict[str, str]]:
    """ZIP_DEFLATED, horodatage fixe. L'empreinte du zip est stable."""
    sommes = "".join(f"{hashlib.sha256(content).hexdigest()}  {name}\n" for name, content in files)
    complet = [*files, ("SHA256SUMS.txt", sommes.encode("utf-8"))]
    empreintes = {name: hashlib.sha256(content).hexdigest() for name, content in complet}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, content in complet:
            info = zipfile.ZipInfo(name, _DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            bundle.writestr(info, content)
    payload = buffer.getvalue()
    return payload, hashlib.sha256(payload).hexdigest(), empreintes
