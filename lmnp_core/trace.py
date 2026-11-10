"""CA6 : chaque case indique ses comptes et les numéros d'écritures sources."""

from __future__ import annotations

from lmnp_core.posting import Ecriture

Filtre = tuple[tuple[str, ...], tuple[str, ...], str]

# (préfixes, exclus, origine). Les exclus évitent de mélanger 213 et 2135.
_FILTRES: dict[tuple[str, str], Filtre] = {
    ("2033-A-SD", "028"): (("21",), (), "brut des immobilisations"),
    ("2033-A-SD", "044"): (("21",), (), "brut des immobilisations"),
    ("2033-A-SD", "030"): (("21", "28"), (), "brut moins amortissements"),
    ("2033-A-SD", "048"): (("21", "28"), (), "brut moins amortissements"),
    ("2033-A-SD", "084"): (("512",), (), "banque"),
    ("2033-A-SD", "086"): (("512",), (), "banque"),
    ("2033-A-SD", "096"): (("512",), (), "actif circulant"),
    ("2033-A-SD", "098"): (("512",), (), "actif circulant"),
    ("2033-A-SD", "110"): (("21", "28", "512"), (), "total brut"),
    ("2033-A-SD", "112"): (("1", "2", "5", "6", "7"), (), "actif net, équilibre du bilan"),
    ("2033-A-SD", "180"): (("1", "2", "5", "6", "7"), (), "passif, équilibre du bilan"),
    ("2033-A-SD", "120"): (("108",), (), "compte de l'exploitant"),
    ("2033-A-SD", "136"): (("6", "7"), (), "résultat de l'exercice"),
    ("2033-A-SD", "142"): (("108", "6", "7"), (), "capitaux propres"),
    ("2033-A-SD", "156"): (("164",), (), "emprunt"),
    ("2033-A-SD", "176"): (("164",), (), "emprunt"),
    ("2033-B-SD", "217"): (("706",), (), "loyers"),
    ("2033-B-SD", "232"): (("7",), ("76", "77"), "produits d'exploitation"),
    ("2033-B-SD", "242"): (("60", "61", "62"), (), "charges externes"),
    ("2033-B-SD", "244"): (("63",), (), "impôts et taxes"),
    ("2033-B-SD", "254"): (("681",), (), "dotations"),
    ("2033-B-SD", "264"): (("6",), ("66", "67"), "charges d'exploitation"),
    ("2033-B-SD", "270"): (("6", "7"), ("66", "67", "76", "77"), "résultat d'exploitation"),
    ("2033-B-SD", "280"): (("76",), (), "produits financiers"),
    ("2033-B-SD", "294"): (("66", "67"), (), "charges financières"),
    ("2033-B-SD", "312"): (("6", "7"), (), "résultat comptable"),
    ("2033-B-SD", "314"): (("6", "7"), (), "résultat comptable"),
    ("2033-B-SD", "318"): (("681",), (), "quote-part non déduite, article 39 C"),
    ("2033-B-SD", "330"): ((), (), "réintégrations : aucune en v1"),
    ("2033-B-SD", "350"): ((), (), "stock 39 C des exercices antérieurs, repris par le moteur"),
    ("2033-B-SD", "352"): (("6", "7"), (), "résultat fiscal avant déficits antérieurs"),
    ("2033-B-SD", "354"): (("6", "7"), (), "résultat fiscal avant déficits antérieurs"),
    ("2033-B-SD", "370"): (("6", "7"), (), "résultat fiscal avant déficits antérieurs"),
    ("2033-B-SD", "372"): (("6", "7"), (), "résultat fiscal avant déficits antérieurs"),
    ("2033-C-SD", "420"): (("211",), (), "terrain"),
    ("2033-C-SD", "422"): (("211",), (), "terrain"),
    ("2033-C-SD", "426"): (("211",), (), "terrain"),
    ("2033-C-SD", "430"): (("213",), ("2135",), "constructions"),
    ("2033-C-SD", "432"): (("213",), ("2135",), "constructions"),
    ("2033-C-SD", "436"): (("213",), ("2135",), "constructions"),
    ("2033-C-SD", "450"): (("2135",), (), "agencements"),
    ("2033-C-SD", "452"): (("2135",), (), "agencements"),
    ("2033-C-SD", "456"): (("2135",), (), "agencements"),
    ("2033-C-SD", "470"): (("218",), (), "autres immobilisations"),
    ("2033-C-SD", "472"): (("218",), (), "autres immobilisations"),
    ("2033-C-SD", "476"): (("218",), (), "autres immobilisations"),
    ("2033-C-SD", "490"): (("211", "213", "218"), (), "total brut"),
    ("2033-C-SD", "492"): (("211", "213", "218"), (), "total brut"),
    ("2033-C-SD", "496"): (("211", "213", "218"), (), "total brut"),
    ("2033-C-SD", "520"): (("2813",), ("28135",), "amortissement des constructions"),
    ("2033-C-SD", "522"): (("2813",), ("28135",), "amortissement des constructions"),
    ("2033-C-SD", "526"): (("2813",), ("28135",), "amortissement des constructions"),
    ("2033-C-SD", "540"): (("28135",), (), "amortissement des agencements"),
    ("2033-C-SD", "542"): (("28135",), (), "amortissement des agencements"),
    ("2033-C-SD", "546"): (("28135",), (), "amortissement des agencements"),
    ("2033-C-SD", "560"): (("2818",), (), "amortissement des autres immobilisations"),
    ("2033-C-SD", "562"): (("2818",), (), "amortissement des autres immobilisations"),
    ("2033-C-SD", "566"): (("2818",), (), "amortissement des autres immobilisations"),
    ("2033-C-SD", "570"): (("28",), (), "total des amortissements"),
    ("2033-C-SD", "572"): (("28",), (), "total des amortissements"),
    ("2033-C-SD", "576"): (("28",), (), "total des amortissements"),
    ("2033-E-SD", "106"): (("706",), (), "ventes de services"),
    ("2033-E-SD", "108"): (("7",), ("76", "77"), "production"),
    ("2033-E-SD", "117"): (("76",), (), "produits financiers"),
    ("2033-E-SD", "121"): (("60", "61", "62"), (), "achats"),
    ("2033-E-SD", "125"): (("60", "61", "62"), (), "charges externes"),
    ("2033-E-SD", "135"): (("681",), (), "dotations"),
    ("2033-E-SD", "137"): (("6", "7"), ("66", "67", "76", "77"), "valeur ajoutée et résultat"),
    ("2033-E-SD", "144"): (("76",), (), "produits financiers"),
    ("2033-E-SD", "146"): (("66",), (), "charges financières"),
    ("2033-E-SD", "152"): (("6",), ("66", "67"), "charges d'exploitation"),
    ("2042-C-PRO", "5NA"): (("6", "7"), (), "bénéfice fiscal avant déficits antérieurs"),
    ("2042-C-PRO", "5NY"): (("6", "7"), (), "déficit fiscal de l'exercice, avant report"),
}


def traces_de(cases: dict[str, int], entries: list[Ecriture]) -> dict[str, dict[str, object]]:
    index = _index(entries)
    out: dict[str, dict[str, object]] = {}
    for key in cases:
        form, _, case = key.partition("/")
        filtre = _FILTRES.get((form, case))
        if filtre is None and form.startswith("2031"):
            filtre = (("6", "7"), (), "résultat fiscal repris sur la 2031")
        if filtre is None and form == "2042-C-PRO":
            filtre = ((), (), f"stock de déficit antérieur, case {case}, pas une écriture de N")
        if filtre is None:
            filtre = ((), (), "case calculée par le mapping 2025")
        prefixes, exclus, origine = filtre
        comptes, ecritures = _touches(index, prefixes, exclus)
        out[key] = {"comptes": comptes, "ecritures": ecritures, "origine": origine}
    return out


def _index(entries: list[Ecriture]) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for entry in entries:
        for line in entry.lignes:
            bucket = found.setdefault(line.compte, [])
            if entry.numero not in bucket:
                bucket.append(entry.numero)
    return found


def _touches(
    index: dict[str, list[int]], prefixes: tuple[str, ...], exclus: tuple[str, ...]
) -> tuple[list[str], list[int]]:
    if not prefixes:
        return [], []
    comptes = sorted(compte for compte in index if _garde(compte, prefixes, exclus))
    numeros: list[int] = []
    for compte in comptes:
        for numero in index[compte]:
            if numero not in numeros:
                numeros.append(numero)
    return comptes, numeros


def _garde(compte: str, prefixes: tuple[str, ...], exclus: tuple[str, ...]) -> bool:
    return compte.startswith(prefixes) and not compte.startswith(exclus)
