"""Current dossier status for the single activity, from closing and export posture."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.dossier import public_dossier
from app.models import FiscalYear
from app.services.export_gate import export_status


def current_dossier(session: Session) -> dict[str, Any]:
    """Latest open exercise, or the latest exercise when every year is closed."""
    years = session.scalars(
        select(FiscalYear).order_by(FiscalYear.year.desc(), FiscalYear.id.desc())
    ).all()
    if not years:
        return public_dossier(
            year_status=None,
            output_status=None,
            exports=None,
            produced=False,
            fiscal_year_id=None,
            year=None,
        )
    active = next((item for item in years if item.status != "CLOSED"), years[0])
    posture = export_status(session, active.id)
    exports = posture.get("exports")
    output_status = posture.get("output_status")
    return public_dossier(
        year_status=active.status,
        output_status=output_status if isinstance(output_status, str) else None,
        exports=exports if isinstance(exports, dict) else None,
        produced=bool(posture.get("produced")),
        fiscal_year_id=active.id,
        year=active.year,
    )
