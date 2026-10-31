from app.domain.filing.acknowledgements import acknowledgements_match

BALANCE = {
    "code": "CLASSEMENT_INCOMPLET",
    "message": "Des comptes de bilan ne sont pas détaillés sur les cases LMNP du 2033-A.",
}
INCOME = {
    "code": "CLASSEMENT_INCOMPLET",
    "message": "Des produits hors loyers ne sont pas détaillés sur le 2033-E.",
}


def test_unique_codes_accept_the_code_or_the_token() -> None:
    warnings = [{"code": "FISCAL_RESEARCH", "message": "Statut Recherche."}]
    assert acknowledgements_match(warnings, ["FISCAL_RESEARCH"])
    assert acknowledgements_match(warnings, ["FISCAL_RESEARCH\nStatut Recherche."])
    assert not acknowledgements_match(warnings, [])


def test_duplicate_codes_need_both_messages() -> None:
    warnings = [BALANCE, INCOME]
    assert not acknowledgements_match(warnings, ["CLASSEMENT_INCOMPLET"])
    assert not acknowledgements_match(warnings, ["CLASSEMENT_INCOMPLET", "CLASSEMENT_INCOMPLET"])
    balance = "CLASSEMENT_INCOMPLET\n" + str(BALANCE["message"])
    income = "CLASSEMENT_INCOMPLET\n" + str(INCOME["message"])
    assert acknowledgements_match(warnings, [balance, income])
