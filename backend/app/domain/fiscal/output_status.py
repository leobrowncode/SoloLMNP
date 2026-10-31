"""User-facing trust of a fiscal output.

Closing, the liasse, the PDF, the spreadsheet and the control archive all read
this module. A vintage stays in Recherche until `fiscal/<year>/validation.json`
records an official source, a date, a scope and a version that still matches
`rules.yaml`. Nothing in that file is marked validated today.

`exports.*.posture` is Provisoire, Bloquée or Finale. `download` is false only
for Bloquée. Download routes refuse that slot; they do not recompute the gates.

The FEC and the control archive follow the liasse. They are Finale only when
the liasse is Finale. An open year, a missing SIREN or an invalid FEC blocks
them. A research or blocked liasse never yields a final FEC.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import Any

from app.core.config import PROJECT_ROOT

OUTPUT_RECHERCHE = "recherche"
OUTPUT_PROVISOIRE = "provisoire"
OUTPUT_DECLARABLE = "declarable"
TRUSTS = (OUTPUT_RECHERCHE, OUTPUT_PROVISOIRE, OUTPUT_DECLARABLE)

POSTURE_PROVISOIRE = "provisoire"
POSTURE_BLOQUEE = "bloquee"
POSTURE_FINALE = "finale"
POSTURES = (POSTURE_PROVISOIRE, POSTURE_BLOQUEE, POSTURE_FINALE)

LABELS = {
    OUTPUT_RECHERCHE: "Recherche",
    OUTPUT_PROVISOIRE: "Provisoire",
    OUTPUT_DECLARABLE: "Déclarable",
}
POSTURE_LABELS = {
    POSTURE_PROVISOIRE: "Provisoire",
    POSTURE_BLOQUEE: "Bloquée",
    POSTURE_FINALE: "Finale",
}
READY_PHRASE = "prête à recopier"
_MANAGED_WARNINGS = frozenset({"RESEARCH_ONLY", "OUTPUT_PROVISOIRE"})


def allows_ready_phrase(trust: str) -> bool:
    """« Prête à recopier » exists only for a Déclarable output."""
    return trust == OUTPUT_DECLARABLE


def load_validation(vintage: str) -> dict[str, Any]:
    """Read `fiscal/<vintage>/validation.json`. Unusable files stay in Recherche."""
    if not vintage.isdigit() or len(vintage) != 4:
        return _research_record(vintage, "UNKNOWN_VINTAGE")
    path = PROJECT_ROOT / "fiscal" / vintage / "validation.json"
    if not path.is_file():
        return _research_record(vintage, "VALIDATION_MISSING")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _research_record(vintage, "VALIDATION_UNREADABLE")
    if not isinstance(document, dict) or document.get("vintage") != vintage:
        return _research_record(vintage, "VALIDATION_MISMATCH")
    return document


def is_validated(record: Mapping[str, Any]) -> bool:
    """True only when the attestation itself is complete. Rules alignment is separate."""
    if record.get("status") != "validated" or record.get("declarable") is not True:
        return False
    vintage = record.get("vintage")
    version = record.get("version")
    rules_version = record.get("rules_version")
    if not isinstance(vintage, str) or not vintage.isdigit() or len(vintage) != 4:
        return False
    if not _text(version) or not _text(rules_version):
        return False
    source = record.get("official_source")
    if not isinstance(source, dict):
        return False
    url = source.get("url")
    if not _text(source.get("reference")) or not isinstance(url, str):
        return False
    if not url.startswith("https://") or len(url) <= len("https://"):
        return False
    validated_on = record.get("validated_on")
    if not isinstance(validated_on, str):
        return False
    try:
        date.fromisoformat(validated_on)
    except ValueError:
        return False
    scope = record.get("scope")
    if not isinstance(scope, dict):
        return False
    excluded = scope.get("excluded")
    if not _text(scope.get("activity")) or not _text(scope.get("regime")):
        return False
    if not isinstance(excluded, list) or not excluded:
        return False
    return all(_text(item) for item in excluded)


def rules_version(vintage: str) -> str | None:
    path = PROJECT_ROOT / "fiscal" / vintage / "rules.yaml"
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    version = document.get("version")
    return version if _text(version) else None


def rules_aligned(record: Mapping[str, Any]) -> bool:
    vintage = record.get("vintage")
    recorded = record.get("rules_version")
    if not isinstance(vintage, str) or not _text(recorded):
        return False
    return recorded == rules_version(vintage)


def resolve_trust(*, record_valid: bool, rules_aligned: bool, copy_complete: bool) -> str:
    if not record_valid:
        return OUTPUT_RECHERCHE
    if not rules_aligned or not copy_complete:
        return OUTPUT_PROVISOIRE
    return OUTPUT_DECLARABLE


def artifact_posture(*, produced: bool, blocked: bool, final: bool) -> str:
    """#49 posture. Bloquée wins over Finale. Callers decide what final means."""
    if not produced or blocked:
        return POSTURE_BLOQUEE
    if final:
        return POSTURE_FINALE
    return POSTURE_PROVISOIRE


def controlled_fec_posture(*, liasse: str, year_closed: bool, fec_blocked: bool) -> str:
    """FEC and control archive. Same posture as the liasse, or Bloquée if stricter.

    Finale exists only when the liasse itself is Finale. An open year, a missing
    SIREN or an invalid FEC stays Bloquée: that file is not ready to send.
    """
    if liasse not in POSTURES:
        liasse = POSTURE_BLOQUEE
    if not year_closed or fec_blocked or liasse == POSTURE_BLOQUEE:
        return POSTURE_BLOQUEE
    if liasse == POSTURE_FINALE:
        return POSTURE_FINALE
    return POSTURE_PROVISOIRE


def classify(
    *,
    validation: Mapping[str, Any],
    copy_complete: bool,
    year_closed: bool,
    produced: bool,
    fec_blocked: bool | None = None,
) -> dict[str, Any]:
    """Single classification used by the calculation, the liasse and the precheck.

    The calculation passes `copy_complete=True`: case gates belong to the liasse.
    A validated calculation can therefore read Déclarable while the liasse stays
    Provisoire. Only the liasse headline may say « Prête à recopier ».
    """
    record_valid = is_validated(validation)
    aligned = rules_aligned(validation)
    trust = resolve_trust(
        record_valid=record_valid,
        rules_aligned=aligned,
        copy_complete=copy_complete,
    )
    shown = presentation(trust, copy_complete=copy_complete)
    liasse_blocked = not copy_complete
    liasse_final = trust == OUTPUT_DECLARABLE and year_closed and copy_complete
    fec_extra_blocked = False if fec_blocked is None else fec_blocked
    liasse = artifact_posture(produced=produced, blocked=liasse_blocked, final=liasse_final)
    fec = controlled_fec_posture(
        liasse=liasse,
        year_closed=year_closed,
        fec_blocked=fec_extra_blocked,
    )
    return {
        "output_status": trust,
        "output_label": shown["output_label"],
        "output_headline": shown["output_headline"],
        "disclaimer": shown["disclaimer"],
        "declarable": trust == OUTPUT_DECLARABLE,
        "copy_complete": copy_complete,
        "export_posture": liasse,
        "export_posture_label": POSTURE_LABELS[liasse],
        "exports": {
            "liasse": _named(liasse),
            "pdf": _named(liasse),
            "fec": _named(fec),
            "archive": _named(fec),
        },
        "validation": _public_validation(validation, effective=record_valid and aligned),
    }


def calculation_status(vintage: str) -> dict[str, Any]:
    """Trust of a stored computation. Case gates are not applied here."""
    return classify(
        validation=load_validation(vintage),
        copy_complete=True,
        year_closed=False,
        produced=True,
    )


def presentation(trust: str, *, copy_complete: bool) -> dict[str, str]:
    if trust == OUTPUT_DECLARABLE:
        return {
            "output_label": LABELS[OUTPUT_DECLARABLE],
            "output_headline": f"{LABELS[OUTPUT_DECLARABLE]} — Prête à recopier",
            "disclaimer": (
                "Feuille prête à recopier dans votre espace professionnel impots.gouv.fr. "
                "Aucun envoi n’est effectué par SoloLMNP."
            ),
        }
    if trust == OUTPUT_PROVISOIRE:
        return {
            "output_label": LABELS[OUTPUT_PROVISOIRE],
            "output_headline": LABELS[OUTPUT_PROVISOIRE],
            "disclaimer": (
                "Sortie provisoire : le millésime est validé, mais cette feuille n’est pas "
                "déclarable. Ne la recopiez pas. Aucun envoi n’est effectué par SoloLMNP."
            ),
        }
    extra = ""
    if copy_complete:
        extra = (
            " Les contrôles internes de la feuille sont satisfaits ; "
            "ils ne valident pas le millésime."
        )
    return {
        "output_label": LABELS[OUTPUT_RECHERCHE],
        "output_headline": LABELS[OUTPUT_RECHERCHE],
        "disclaimer": (
            "Sortie de recherche. Ce millésime n’est pas validé : ne recopiez pas "
            "ces montants dans une déclaration."
            + extra
            + " Aucun envoi n’est effectué par SoloLMNP."
        ),
    }


def apply_output_status(
    package: dict[str, Any],
    *,
    year_closed: bool,
    fec_blocked: bool | None = None,
) -> None:
    """Stamp a compiled package. Safe to call again, including on a frozen snapshot."""
    if "copy_complete" not in package:
        package["copy_complete"] = (
            package.get("status") == "ready"
            and package.get("declarable") is True
            and not package.get("errors")
        )
    summary = classify(
        validation=load_validation(str(package.get("vintage") or "")),
        copy_complete=bool(package["copy_complete"]),
        year_closed=year_closed,
        produced=True,
        fec_blocked=fec_blocked,
    )
    package.update(summary)
    trust = str(summary["output_status"])
    package["status"] = "research_only" if trust == OUTPUT_RECHERCHE else trust
    field_status = "research_only" if trust == OUTPUT_RECHERCHE else trust
    for field in package.get("fields", []):
        if isinstance(field, dict):
            field["status"] = field_status
    _replace_trust_warning(package, trust)


def contains_ready_phrase(text: str) -> bool:
    return READY_PHRASE in text.casefold()


def _replace_trust_warning(package: dict[str, Any], trust: str) -> None:
    warnings = [
        item
        for item in package.get("warnings", [])
        if not isinstance(item, dict) or item.get("code") not in _MANAGED_WARNINGS
    ]
    if trust == OUTPUT_RECHERCHE:
        warnings.append(
            {
                "code": "RESEARCH_ONLY",
                "message": (
                    "Millésime en recherche : cette feuille n’est pas une base de déclaration. "
                    "SoloLMNP n’envoie rien aux impôts."
                ),
            }
        )
    elif trust == OUTPUT_PROVISOIRE:
        warnings.append(
            {
                "code": "OUTPUT_PROVISOIRE",
                "message": (
                    "Sortie provisoire : le millésime est validé, "
                    "mais cette feuille n’est pas déclarable."
                ),
            }
        )
    package["warnings"] = warnings


def _public_validation(record: Mapping[str, Any], *, effective: bool) -> dict[str, Any]:
    source = record.get("official_source")
    scope = record.get("scope")
    return {
        "vintage": record.get("vintage"),
        "version": record.get("version"),
        "status": record.get("status"),
        "official_source": source if isinstance(source, dict) else None,
        "validated_on": record.get("validated_on"),
        "scope": scope if isinstance(scope, dict) else None,
        "rules_version": record.get("rules_version"),
        "effective": effective,
    }


def export_slot(posture: str) -> dict[str, Any]:
    """One export as the API and the screen share it. Unknown values stay Bloquée."""
    if posture not in POSTURES:
        posture = POSTURE_BLOQUEE
    return {
        "posture": posture,
        "label": POSTURE_LABELS[posture],
        "download": posture != POSTURE_BLOQUEE,
    }


def align_controlled_exports(
    exports: Mapping[str, Any],
    *,
    year_closed: bool,
    fec_blocked: bool,
) -> dict[str, Any]:
    """Keep liasse and PDF slots. FEC and the archive never outrank the liasse."""
    stamped: dict[str, Any] = {}
    for key, value in exports.items():
        posture = POSTURE_BLOQUEE
        if isinstance(value, dict):
            raw = value.get("posture")
            if isinstance(raw, str):
                posture = raw
        stamped[key] = export_slot(posture)
    liasse = stamped.get("liasse", export_slot(POSTURE_BLOQUEE))
    fec = controlled_fec_posture(
        liasse=str(liasse.get("posture") or POSTURE_BLOQUEE),
        year_closed=year_closed,
        fec_blocked=fec_blocked,
    )
    shared = export_slot(fec)
    stamped["fec"] = shared
    stamped["archive"] = shared
    return stamped


def download_refusal(kind: str, status: Mapping[str, Any]) -> dict[str, Any] | None:
    """None when the slot says download is allowed. Otherwise the structured refusal."""
    exports = status.get("exports")
    slot = exports.get(kind) if isinstance(exports, dict) else None
    if isinstance(slot, dict) and slot.get("download") is True:
        return None
    family = "fec" if kind in {"fec", "archive"} else "liasse"
    raw = status.get("prerequisites")
    matched = (
        [item for item in raw if isinstance(item, dict) and item.get("export") in {kind, family}]
        if isinstance(raw, list)
        else []
    )
    if not matched:
        return {
            "code": "EXPORT_BLOCKED",
            "message": "Ce téléchargement est bloqué.",
            "action": {"label": "Voir la liasse", "href": "/fiscalite#sorties-figees"},
        }
    primary = matched[0]
    refusal: dict[str, Any] = {
        "code": str(primary.get("code") or "EXPORT_BLOCKED"),
        "message": str(primary.get("message") or "Ce téléchargement est bloqué."),
    }
    action = primary.get("action")
    if isinstance(action, dict):
        label = action.get("label")
        href = action.get("href")
        if isinstance(label, str) and isinstance(href, str):
            refusal["action"] = {"label": label, "href": href}
    if len(matched) > 1:
        refusal["code"] = "EXPORT_BLOCKED"
        refusal["message"] = (
            "La liasse indique des prérequis manquants."
            if family == "liasse"
            else "Le FEC et le dossier de contrôle indiquent des prérequis manquants."
        )
        refusal["issues"] = [
            {
                "code": str(item.get("code") or "EXPORT_BLOCKED"),
                "message": str(item.get("message") or ""),
            }
            for item in matched
        ]
    return refusal


def _named(posture: str) -> dict[str, Any]:
    return export_slot(posture)


def _research_record(vintage: str, defect: str) -> dict[str, Any]:
    return {
        "vintage": vintage,
        "version": None,
        "status": "research_only",
        "declarable": False,
        "official_source": None,
        "validated_on": None,
        "scope": None,
        "rules_version": None,
        "defect": defect,
    }


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())
