"""Dossier board: one state per step, from facts already decided elsewhere.

Shipped vintages stay ``research_only``. This view never says déclarable.
Amounts that travel with a step are integer cents.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

STEP_IDS = ("structure", "operations", "assets", "opening", "closing", "filing")

STATUS_A_FAIRE = "a_faire"
STATUS_EN_COURS = "en_cours"
STATUS_BLOQUE = "bloque"
STATUS_PRET = "pret"
STATUS_FAIT = "fait"

STATUS_LABELS = {
    STATUS_A_FAIRE: "À faire",
    STATUS_EN_COURS: "En cours",
    STATUS_BLOQUE: "Bloqué",
    STATUS_PRET: "Prête",
    STATUS_FAIT: "Terminé",
}

_POSTURE_LABELS = {"provisoire": "Provisoire", "bloquee": "Bloquée", "finale": "Finale"}
_PROGRESS_CODES = frozenset(
    {
        "YEAR_DRAFTS",
        "CENTRALIZATION_REQUIRED",
        "DEPRECIATION_UNPOSTED",
        "FISCAL_NOT_COMPUTED",
        "FISCAL_STALE",
    }
)
_FROZEN = frozenset({"READY_TO_CLOSE", "CLOSED"})

# Same destinations as the disabled-action explanations (actionCauses FIX / PRECHECK).
_LINKS: dict[str, tuple[str, str]] = {
    "NO_ACTIVITY": ("Créer l’activité", "/comptabilite/brouillons#creer-activite"),
    "NO_YEAR": ("Créer un exercice", "/comptabilite/brouillons#ajouter-exercice"),
    "NO_PROPERTY": ("Ajouter un bien", "/operations/biens#ajouter-bien"),
    "NO_BANK": ("Ajouter un compte bancaire", "/operations/banque#ajouter-banque"),
    "NO_ASSET": ("Nouvelle immobilisation", "/immobilisations#nouvelle-immobilisation"),
    "NO_PERIOD": ("Calculer les périodes", "/immobilisations#calculer-periodes"),
    "SIREN_REQUIRED": ("Renseigner le SIREN", "/comptabilite/brouillons#identite-liasse"),
    "SIREN_MANQUANT": ("Renseigner le SIREN", "/comptabilite/brouillons#identite-liasse"),
    "YEAR_DRAFTS": ("Valider les brouillons", "/comptabilite/brouillons#nouvelle-ecriture"),
    "DEPRECIATION_UNPOSTED": ("Comptabiliser les dotations", "/immobilisations#dotations"),
    "FISCAL_NOT_COMPUTED": ("Calculer le résultat fiscal", "/fiscalite#calcul-fiscal"),
    "FISCAL_STALE": ("Calculer le résultat fiscal", "/fiscalite#calcul-fiscal"),
    "CENTRALIZATION_REQUIRED": ("Centraliser le résultat", "/etats-comptables#result-title"),
    "SOURCE_NOT_CLOSED": ("Clôturer l’exercice précédent", "/fiscalite#close-title"),
    "TARGET_HAS_ENTRIES": ("Consulter le journal", "/comptabilite/journal"),
    "OPENING_MISSING": ("Prévisualiser les à-nouveaux", "/etats-comptables#opening-title"),
    "YEAR_NOT_CLOSED": ("Clôturer l’exercice", "/fiscalite#close-title"),
}
_PRECHECK_LINK = ("Voir le pré-contrôle", "/fiscalite#close-title")

_FALLBACK: dict[str, tuple[str, str]] = {
    "structure": ("ouvrir la comptabilité", "/comptabilite/brouillons"),
    "operations": ("ouvrir les opérations", "/operations/biens"),
    "assets": ("ouvrir les immobilisations", "/immobilisations"),
    "opening": ("prévisualiser les à-nouveaux", "/etats-comptables#opening-title"),
    "closing": ("voir le pré-contrôle", "/fiscalite#close-title"),
    "filing": ("ouvrir la fiscalité", "/fiscalite#calcul-fiscal"),
}


@dataclass(frozen=True)
class EventFact:
    step: str
    occurred_at: datetime
    label: str


@dataclass(frozen=True)
class PrerequisiteFact:
    code: str
    message: str
    export: str
    action_label: str
    action_href: str


@dataclass(frozen=True)
class DashboardFacts:
    activity_present: bool
    siren_present: bool
    year_id: int | None
    year: int | None
    year_status: str | None
    property_count: int
    bank_count: int
    operation_count: int
    operation_amount_cents: int
    draft_count: int
    asset_count: int
    depreciable_asset_count: int
    calculated_period_count: int
    posted_period_count: int
    posted_depreciation_cents: int
    has_previous_year: bool
    previous_year_closed: bool
    opening_posted: bool
    opening_amount_cents: int
    target_has_entries: bool
    fiscal_produced: bool
    fiscal_stale: bool
    fiscal_result_cents: int | None
    close_errors: tuple[tuple[str, str], ...]
    exports: Mapping[str, Any]
    export_prerequisites: tuple[PrerequisiteFact, ...]
    events: tuple[EventFact, ...]
    dossier: Mapping[str, Any]


def build_dashboard(facts: DashboardFacts) -> dict[str, Any]:
    """Public board. ``dossier`` is the status already computed for the banner."""
    if facts.dossier.get("vintage_status") != "research_only":
        raise ValueError("Millésime hors recherche.")
    steps = [
        _structure(facts),
        _operations(facts),
        _assets(facts),
        _opening(facts),
        _closing(facts),
        _filing(facts),
    ]
    action = _continue(facts, steps)
    payload = {
        "dossier": dict(facts.dossier),
        "continue": action,
        "steps": steps,
        "progression": _progression(steps, action),
    }
    return _guard(payload)


def _structure(facts: DashboardFacts) -> dict[str, Any]:
    prerequisites: list[dict[str, Any]] = []
    if not facts.activity_present:
        status = STATUS_A_FAIRE
        prerequisites.append(_cause("NO_ACTIVITY", "L’activité n’est pas créée."))
    elif facts.year_id is None:
        status = STATUS_EN_COURS
        prerequisites.append(_cause("NO_YEAR", "Aucun exercice n’est créé."))
    elif not facts.siren_present:
        prerequisites.append(_cause("SIREN_REQUIRED", "Le SIREN n’est pas renseigné."))
        blocked = facts.fiscal_produced or facts.year_status == "CLOSED"
        status = STATUS_BLOQUE if blocked else STATUS_EN_COURS
    else:
        status = STATUS_FAIT
    if status == STATUS_FAIT:
        summary = f"Activité, exercice {facts.year} et SIREN sont en place."
    else:
        summary = str(prerequisites[0]["message"])
    return _step(facts, "structure", "Structure et SIREN", status, summary, prerequisites, None)


def _operations(facts: DashboardFacts) -> dict[str, Any]:
    amount = facts.operation_amount_cents if facts.operation_count else None
    if facts.year_status in _FROZEN:
        if facts.operation_count:
            summary = "Des opérations sont enregistrées. La saisie est figée."
        else:
            summary = "La saisie de l’exercice est figée."
        return _step(facts, "operations", "Opérations", STATUS_FAIT, summary, [], amount)
    prerequisites: list[dict[str, Any]] = []
    if not facts.activity_present:
        prerequisites.append(_cause("NO_ACTIVITY", "L’activité n’est pas créée."))
    if facts.year_id is None:
        prerequisites.append(_cause("NO_YEAR", "Aucun exercice n’est créé."))
    if facts.property_count == 0:
        prerequisites.append(_cause("NO_PROPERTY", "Aucun bien n’est enregistré."))
    if facts.bank_count == 0 and facts.operation_count == 0 and facts.year_status == "OPEN":
        prerequisites.append(_cause("NO_BANK", "Aucun compte bancaire n’est enregistré."))
    if facts.draft_count > 0:
        prerequisites.append(_cause("YEAR_DRAFTS", "Des brouillons sont encore ouverts."))
    if not facts.activity_present or facts.year_id is None or facts.property_count == 0:
        status = STATUS_A_FAIRE
    elif facts.operation_count == 0 or facts.draft_count > 0:
        status = STATUS_EN_COURS
    else:
        status = STATUS_FAIT
    if status == STATUS_FAIT:
        summary = "Des opérations sont enregistrées."
    elif prerequisites:
        summary = str(prerequisites[0]["message"])
    else:
        summary = "Les opérations de l’exercice sont à poursuivre."
    return _step(facts, "operations", "Opérations", status, summary, prerequisites, amount)


def _assets(facts: DashboardFacts) -> dict[str, Any]:
    amount = facts.posted_depreciation_cents if facts.posted_period_count else None
    prerequisites: list[dict[str, Any]] = []
    if facts.property_count == 0:
        prerequisites.append(_cause("NO_PROPERTY", "Aucun bien n’est enregistré."))
        status = STATUS_A_FAIRE
        summary = str(prerequisites[0]["message"])
    elif facts.asset_count == 0:
        prerequisites.append(_cause("NO_ASSET", "Aucune immobilisation n’est enregistrée."))
        status = STATUS_EN_COURS
        summary = str(prerequisites[0]["message"])
    elif facts.year_id is None:
        prerequisites.append(_cause("NO_YEAR", "Aucun exercice n’est créé."))
        status = STATUS_EN_COURS
        summary = str(prerequisites[0]["message"])
    elif facts.depreciable_asset_count > 0 and _period_total(facts) == 0:
        prerequisites.append(_cause("NO_PERIOD", "Aucune période d’amortissement n’est calculée."))
        status = STATUS_EN_COURS
        summary = str(prerequisites[0]["message"])
    elif facts.calculated_period_count > 0:
        prerequisites.append(
            _cause(
                "DEPRECIATION_UNPOSTED",
                "Des dotations calculées ne sont pas comptabilisées.",
            )
        )
        hard = facts.year_status in _FROZEN or _has_code(facts, "DEPRECIATION_UNPOSTED")
        status = STATUS_BLOQUE if hard else STATUS_EN_COURS
        summary = str(prerequisites[0]["message"])
    elif facts.depreciable_asset_count == 0:
        status = STATUS_FAIT
        summary = "Le terrain n’est pas amorti."
    else:
        status = STATUS_FAIT
        summary = "Les dotations de l’exercice sont comptabilisées."
    return _step(
        facts,
        "assets",
        "Immobilisations et amortissements",
        status,
        summary,
        prerequisites,
        amount,
    )


def _opening(facts: DashboardFacts) -> dict[str, Any]:
    if not facts.activity_present:
        return _blocked_start(
            facts, "opening", "À-nouveaux", "NO_ACTIVITY", "L’activité n’est pas créée."
        )
    if facts.year_id is None:
        return _blocked_start(
            facts, "opening", "À-nouveaux", "NO_YEAR", "Aucun exercice n’est créé."
        )
    if not facts.has_previous_year:
        return _step(
            facts,
            "opening",
            "À-nouveaux",
            STATUS_FAIT,
            "Premier exercice : aucun à-nouveaux à reprendre.",
            [],
            None,
        )
    if not facts.previous_year_closed:
        prerequisites = [
            _cause(
                "SOURCE_NOT_CLOSED",
                "L’exercice précédent n’est pas clôturé : ces soldes peuvent changer.",
            )
        ]
        return _step(
            facts,
            "opening",
            "À-nouveaux",
            STATUS_BLOQUE,
            prerequisites[0]["message"],
            prerequisites,
            None,
        )
    if facts.opening_posted:
        return _step(
            facts,
            "opening",
            "À-nouveaux",
            STATUS_FAIT,
            "Les à-nouveaux sont comptabilisés.",
            [],
            facts.opening_amount_cents,
        )
    if facts.target_has_entries:
        prerequisites = [
            _cause(
                "TARGET_HAS_ENTRIES",
                "L’exercice destinataire contient déjà des écritures : "
                "vérifier les reprises existantes avant toute génération.",
            )
        ]
        return _step(
            facts,
            "opening",
            "À-nouveaux",
            STATUS_BLOQUE,
            prerequisites[0]["message"],
            prerequisites,
            None,
        )
    prerequisites = [_cause("OPENING_MISSING", "Les à-nouveaux ne sont pas comptabilisés.")]
    return _step(
        facts,
        "opening",
        "À-nouveaux",
        STATUS_EN_COURS,
        prerequisites[0]["message"],
        prerequisites,
        None,
    )


def _closing(facts: DashboardFacts) -> dict[str, Any]:
    if not facts.activity_present:
        return _blocked_start(
            facts, "closing", "Clôture", "NO_ACTIVITY", "L’activité n’est pas créée."
        )
    if facts.year_id is None:
        return _blocked_start(facts, "closing", "Clôture", "NO_YEAR", "Aucun exercice n’est créé.")
    if facts.year_status == "CLOSED":
        return _step(facts, "closing", "Clôture", STATUS_FAIT, "Exercice clôturé.", [], None)
    prerequisites = [_close_cause(code, message) for code, message in facts.close_errors]
    if facts.year_status == "READY_TO_CLOSE" and not prerequisites:
        return _step(
            facts,
            "closing",
            "Clôture",
            STATUS_PRET,
            "Exercice prêt à clôturer.",
            [],
            None,
        )
    if prerequisites:
        hard = any(item["code"] not in _PROGRESS_CODES for item in prerequisites)
        if facts.year_status == "READY_TO_CLOSE":
            hard = True
        status = STATUS_BLOQUE if hard else STATUS_EN_COURS
        summary = str(prerequisites[0]["message"])
        return _step(facts, "closing", "Clôture", status, summary, prerequisites, None)
    return _step(
        facts,
        "closing",
        "Clôture",
        STATUS_PRET,
        "Le pré-contrôle ne bloque pas. Préparez la clôture.",
        [],
        None,
    )


def _filing(facts: DashboardFacts) -> dict[str, Any]:
    if not facts.activity_present:
        prerequisites = [_cause("NO_ACTIVITY", "L’activité n’est pas créée.")]
        return _step(
            facts,
            "filing",
            "Fiscalité et exports",
            STATUS_A_FAIRE,
            prerequisites[0]["message"],
            prerequisites,
            None,
        )
    if facts.year_id is None:
        prerequisites = [_cause("NO_YEAR", "Aucun exercice n’est créé.")]
        return _step(
            facts,
            "filing",
            "Fiscalité et exports",
            STATUS_A_FAIRE,
            prerequisites[0]["message"],
            prerequisites,
            None,
        )
    if not facts.fiscal_produced or facts.fiscal_stale:
        if facts.fiscal_stale:
            prerequisites = [
                _cause("FISCAL_STALE", "Le calcul fiscal ne correspond plus au ledger.")
            ]
        else:
            prerequisites = [_fiscal_missing(facts)]
        return _step(
            facts,
            "filing",
            "Fiscalité et exports",
            STATUS_EN_COURS,
            prerequisites[0]["message"],
            prerequisites,
            None,
        )
    liasse_blocked = _posture(facts.exports, "liasse") == "bloquee"
    fec_blocked = _posture(facts.exports, "fec") == "bloquee"
    amount = facts.fiscal_result_cents
    summary = _export_summary(facts)
    if liasse_blocked:
        prerequisites = _export_causes(facts, {"liasse", "pdf"})
        if not prerequisites:
            prerequisites = [
                _cause(
                    "EXPORT_BLOCKED",
                    "La liasse n’est pas téléchargeable tant que les contrôles de cases "
                    "ne sont pas satisfaits.",
                    ("Voir la liasse", "/fiscalite#sorties-figees"),
                )
            ]
        return _step(
            facts, "filing", "Fiscalité et exports", STATUS_BLOQUE, summary, prerequisites, amount
        )
    if facts.year_status == "CLOSED" and fec_blocked:
        prerequisites = _export_causes(facts, {"fec", "archive"})
        if not prerequisites:
            prerequisites = [
                _cause(
                    "EXPORT_BLOCKED",
                    "Le FEC et le dossier de contrôle sont bloqués.",
                    ("Voir le pré-contrôle", "/fiscalite#close-title"),
                )
            ]
        return _step(
            facts, "filing", "Fiscalité et exports", STATUS_BLOQUE, summary, prerequisites, amount
        )
    if facts.year_status == "CLOSED":
        return _step(facts, "filing", "Fiscalité et exports", STATUS_FAIT, summary, [], amount)
    prerequisites = _export_causes(facts, {"fec", "archive"})
    return _step(
        facts, "filing", "Fiscalité et exports", STATUS_PRET, summary, prerequisites, amount
    )


def _blocked_start(
    facts: DashboardFacts, step_id: str, label: str, code: str, message: str
) -> dict[str, Any]:
    prerequisites = [_cause(code, message)]
    return _step(facts, step_id, label, STATUS_A_FAIRE, message, prerequisites, None)


def _step(
    facts: DashboardFacts,
    step_id: str,
    label: str,
    status: str,
    summary: str,
    prerequisites: list[dict[str, Any]],
    amount_cents: int | None,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "summary": summary,
        "prerequisites": prerequisites,
        "last_event": _latest(facts, step_id),
        "amount_cents": amount_cents,
    }


def _continue(facts: DashboardFacts, steps: list[dict[str, Any]]) -> dict[str, Any]:
    """Next action from the first real blocker, then the first unfinished step."""
    blocked = next((step for step in steps if step["status"] == STATUS_BLOQUE), None)
    if blocked is not None and blocked["prerequisites"]:
        return _from_prerequisite(blocked)
    if facts.year_status == "CLOSED":
        return _direct("filing", "/fiscalite#sorties-figees", "voir les sorties")
    if facts.year_status == "READY_TO_CLOSE":
        closing = next(step for step in steps if step["id"] == "closing")
        if closing["status"] != STATUS_BLOQUE:
            return _direct("closing", "/fiscalite#close-title", "confirmer la clôture")
    pending = next((step for step in steps if step["status"] != STATUS_FAIT), None)
    if pending is None:
        return _direct("filing", "/fiscalite#sorties-figees", "voir les sorties")
    if pending["id"] == "closing" and pending["status"] == STATUS_PRET:
        if facts.year_status == "READY_TO_CLOSE":
            return _direct("closing", "/fiscalite#close-title", "confirmer la clôture")
        return _direct("closing", "/fiscalite#close-title", "voir le pré-contrôle")
    if pending["prerequisites"]:
        return _from_prerequisite(pending)
    label, href = _FALLBACK[str(pending["id"])]
    return _direct(str(pending["id"]), href, label)


def _progression(steps: list[dict[str, Any]], action: Mapping[str, Any]) -> dict[str, Any]:
    done = sum(1 for step in steps if step["status"] == STATUS_FAIT)
    total = len(steps)
    current = next(step for step in steps if step["id"] == action["step"])
    return {
        "done": done,
        "total": total,
        "label": f"{done}/{total}",
        "current_step": current["id"],
        "current_label": current["label"],
        "current_status": current["status"],
        "current_status_label": current["status_label"],
        "summary": current["summary"],
    }


def _from_prerequisite(step: Mapping[str, Any]) -> dict[str, Any]:
    action = step["prerequisites"][0]["action"]
    return _direct(str(step["id"]), str(action["href"]), str(action["label"]))


def _direct(step: str, href: str, action_label: str) -> dict[str, Any]:
    return {
        "label": "Continuer",
        "href": href,
        "detail": f"Prochaine action : {action_label}.",
        "step": step,
    }


def _cause(
    code: str,
    message: str,
    link: tuple[str, str] | None = None,
) -> dict[str, Any]:
    label, href = link or _LINKS[code]
    return {"code": code, "message": message, "action": {"label": label, "href": href}}


def _close_cause(code: str, message: str) -> dict[str, Any]:
    return _cause(code, message, _LINKS.get(code, _PRECHECK_LINK))


def _fiscal_missing(facts: DashboardFacts) -> dict[str, Any]:
    for item in facts.export_prerequisites:
        if item.code == "FISCAL_NOT_COMPUTED":
            return _cause(
                item.code,
                item.message,
                (item.action_label, item.action_href),
            )
    return _cause(
        "FISCAL_NOT_COMPUTED",
        "Aucun calcul fiscal n’est enregistré pour cet exercice.",
    )


def _export_causes(facts: DashboardFacts, kinds: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in facts.export_prerequisites:
        if item.export not in kinds:
            continue
        rows.append(_cause(item.code, item.message, (item.action_label, item.action_href)))
    return rows


def _export_summary(facts: DashboardFacts) -> str:
    liasse = _posture_label(facts.exports, "liasse")
    pdf = _posture_label(facts.exports, "pdf")
    fec = _posture_label(facts.exports, "fec")
    return f"Liasse {liasse}. PDF {pdf}. FEC {fec}. Millésime en recherche."


def _posture(exports: Mapping[str, Any], kind: str) -> str:
    slot = exports.get(kind)
    if isinstance(slot, Mapping):
        raw = slot.get("posture")
        if isinstance(raw, str) and raw in _POSTURE_LABELS:
            return raw
    return "bloquee"


def _posture_label(exports: Mapping[str, Any], kind: str) -> str:
    return _POSTURE_LABELS[_posture(exports, kind)]


def _latest(facts: DashboardFacts, step: str) -> dict[str, str] | None:
    rows = [item for item in facts.events if item.step == step]
    if not rows:
        return None
    best = max(enumerate(rows), key=lambda pair: (pair[1].occurred_at, pair[0]))[1]
    return {"occurred_at": _iso(best.occurred_at), "label": best.label}


def _iso(value: datetime) -> str:
    stamp = value.isoformat(timespec="seconds")
    if value.tzinfo is None:
        return stamp + "Z"
    return stamp


def _period_total(facts: DashboardFacts) -> int:
    return facts.calculated_period_count + facts.posted_period_count


def _has_code(facts: DashboardFacts, code: str) -> bool:
    return any(item == code for item, _message in facts.close_errors)


def _guard(payload: dict[str, Any]) -> dict[str, Any]:
    encoded = json.dumps(payload, ensure_ascii=False).lower()
    if "declarable" in encoded or "déclarable" in encoded:
        raise ValueError("Le tableau de bord ne présente pas un dossier déclarable.")
    progress = payload["progression"]
    done = sum(1 for step in payload["steps"] if step["status"] == STATUS_FAIT)
    if progress["done"] != done or progress["total"] != len(payload["steps"]):
        raise ValueError("La progression ne correspond pas aux étapes.")
    if progress["label"] != f"{done}/{progress['total']}":
        raise ValueError("Le libellé de progression ne correspond pas au décompte.")
    if progress["current_step"] != payload["continue"]["step"]:
        raise ValueError("La progression ne correspond pas à la prochaine action.")
    for step in payload["steps"]:
        summary = step["summary"]
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Chaque étape a une justification.")
        if step["status"] != STATUS_BLOQUE:
            continue
        hrefs = [item["action"]["href"] for item in step["prerequisites"]]
        if not hrefs or any(
            not isinstance(href, str) or not href.startswith("/") for href in hrefs
        ):
            raise ValueError("Chaque blocage a un lien correctif.")
    return payload
