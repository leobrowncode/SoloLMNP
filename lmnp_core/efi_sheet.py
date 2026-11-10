"""Feuille de recopie dans l'ordre des écrans EFI. Aucune télétransmission."""

from __future__ import annotations

from lmnp_core.money import euros

# Ordre des écrans du réel simplifié : 2033-A, C, B, D, puis 2031.
ECRANS = (
    ("2033-A-SD", "2033-A"),
    ("2033-C-SD", "2033-C"),
    ("2033-B-SD", "2033-B"),
    ("2033-D-SD", "2033-D"),
    ("2033-E-SD", "2033-E"),
    ("2031-SD", "2031"),
    ("2031-BIS-SD", "2031-bis"),
    ("2042-C-PRO", "2042-C-PRO"),
)


def feuille(cases: dict[str, int], traces: dict[str, dict[str, object]]) -> dict[str, object]:
    lignes: list[dict[str, object]] = []
    controles: list[dict[str, object]] = []
    ordre = 1
    for form, ecran in ECRANS:
        if form == "2033-D-SD":
            lignes.append(_ligne(ordre, ecran, form, "II", None, {}, "neant"))
            ordre += 1
            controles.append(
                {
                    "formulaire": form,
                    "ok": True,
                    "texte": "Cadre II : neant. Le releve des deficits est reserve a l'IS.",
                }
            )
            continue
        bloc = sorted((key, amount) for key, amount in cases.items() if key.startswith(f"{form}/"))
        for key, amount in bloc:
            case = key.split("/", 1)[1]
            trace = traces.get(key, {})
            lignes.append(_ligne(ordre, ecran, form, case, amount, trace, euros(amount)))
            ordre += 1
        controles.append(_controle(form, dict(bloc)))
    return {
        "ordre_ecrans": [ecran for _form, ecran in ECRANS],
        "lignes": lignes,
        "controles": controles,
        "ok": all(item["ok"] for item in controles),
        "transmission": False,
    }


def texte(sheet: dict[str, object], *, nom: str, siret: str) -> str:
    lines = [
        "Feuille de recopie EFI. Document de travail.",
        "A recopier soi-meme sur impots.gouv.fr. Aucune teletransmission.",
        f"Dossier : {nom}. SIRET {siret}.",
        "",
    ]
    ecran = ""
    for row in _dicts(sheet["lignes"]):
        if row["ecran"] != ecran:
            ecran = str(row["ecran"])
            lines.append(f"## {ecran}")
        montant = row["montant"]
        comptes = ", ".join(str(item) for item in row["comptes"]) or "-"
        ecritures = ", ".join(str(item) for item in row["ecritures"]) or "-"
        lines.append(
            f"{row['case']}\t{montant}\tcomptes {comptes}\tecritures {ecritures}\t{row['origine']}"
        )
    lines.append("")
    lines.append("Totaux de controle")
    for item in _dicts(sheet["controles"]):
        lines.append(f"{item['formulaire']}\t{item['texte']}")
    lines.append("")
    return "\n".join(lines)


def _dicts(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise TypeError("Feuille illisible.")
    rows: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("Ligne illisible.")
        rows.append(item)
    return rows


def _ligne(
    ordre: int,
    ecran: str,
    form: str,
    case: str,
    amount: int | None,
    trace: dict[str, object],
    montant: str,
) -> dict[str, object]:
    return {
        "ordre": ordre,
        "ecran": ecran,
        "formulaire": form,
        "case": case,
        "montant_centimes": amount,
        "montant": montant,
        "comptes": list(trace.get("comptes") or []),
        "ecritures": list(trace.get("ecritures") or []),
        "origine": str(trace.get("origine") or ""),
    }


def _controle(form: str, bloc: dict[str, int]) -> dict[str, object]:
    somme = sum(bloc.values())
    if form == "2033-A-SD":
        actif = bloc.get(f"{form}/112")
        passif = bloc.get(f"{form}/180")
        ok = actif is not None and actif == passif
        texte = f"Actif net 112 = passif 180 ({actif}). Somme des cases {somme}."
        return {"formulaire": form, "ok": ok, "texte": texte}
    return {
        "formulaire": form,
        "ok": True,
        "texte": f"{len(bloc)} cases, somme algebrique {somme}.",
    }
