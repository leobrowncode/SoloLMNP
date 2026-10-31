"""Result centralisation stays a ledger fact. A later entry does not rewrite it."""

STALE_CODE = "CENTRALIZATION_STALE"
STALE_MESSAGE = (
    "Des écritures ont modifié le résultat après la centralisation. "
    "Extournez la centralisation dans le journal, puis recentralisez."
)
STALE_ACTION = {
    "label": "Revoir la centralisation",
    "href": "/etats-comptables#result-title",
}


def stale_error() -> dict[str, str]:
    return {"code": STALE_CODE, "message": STALE_MESSAGE}
