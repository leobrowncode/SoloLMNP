"""Manual EFI worksheet. Nothing is sent to the tax authority."""

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.filing import TaxReturnSnapshot
from app.services.ledger import fail, get_year


def efi_worksheet(session: Session, year_id: int) -> dict[str, Any]:
    year = get_year(session, year_id)
    snapshot = session.scalar(
        select(TaxReturnSnapshot).where(
            TaxReturnSnapshot.fiscal_year_id == year.id,
            TaxReturnSnapshot.status == "CURRENT",
        )
    )
    if snapshot is None:
        fail("SNAPSHOT_REQUIRED", "Aucune liasse figée n’est disponible pour cet exercice.", 404)
    assert snapshot is not None  # noqa: S101
    package = json.loads(snapshot.canonical_json)
    return {
        "fiscal_year_id": year.id,
        "declarable": False,
        "transmission": False,
        "snapshot_sha256": snapshot.sha256,
        "disclaimer": (
            "Feuille de recopie uniquement. Aucune case 2042-C-PRO n’est affirmée "
            "tant que la notice du millésime n’est pas archivée. Aucun envoi n’est effectué."
        ),
        "liasse": {
            "form": package["form"],
            "vintage": package["vintage"],
            "fields": [
                {
                    "code": field["code"],
                    "label": field["label"],
                    "value": field["value"],
                    "expression": field["expression"],
                }
                for field in package["fields"]
            ],
        },
        "personal_return": {
            "form": "2042-C-PRO",
            "official_case": None,
            "status": "case_not_verified",
            "amount": package["fiscal_result"],
            "separated_from_liasse": True,
        },
    }
