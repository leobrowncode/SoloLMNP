# Registre des règles fiscales

Consultation initiale : 15 septembre 2026. Ce registre est un inventaire de recherche, **pas une validation pour déclarer**. Chaque règle sera confirmée pour le millésime avant code métier.

| Rule ID | Millésime | Règle/interprétation provisoire | Source officielle | Code/tests | État |
|---|---:|---|---|---|---|
| RULE-LMNP-BIC-001 | 2025+ | La location meublée relève des BIC ; qualification professionnelle/non professionnelle à déterminer selon CGI 155 IV. | [CGI art. 155](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000048844834) ; [BOFiP BOI-BIC-CHAMP-40-10](https://bofip.impots.gouv.fr/bofip/3610-PGP.html) | futur moteur/statut | à revalider |
| RULE-LMNP-DEPRECIATION-LIMIT-001 | 2025+ | Pour la location meublée non professionnelle, la déduction d'amortissement est plafonnée selon CGI 39 C ; l'excédent se suit séparément. La formule exacte doit être dérivée du texte et de la doctrine du millésime. | [CGI art. 39 C](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006307073) ; [BOFiP BOI-BIC-AMT-20-40-10](https://bofip.impots.gouv.fr/bofip/1802-PGP.html) | golden C | recherche |
| RULE-LMNP-LOSS-001 | 2025+ | Les déficits LMNP se reportent séparément des amortissements différés, dans les limites/délais légaux applicables. | [CGI art. 156 I 1° ter](https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000048844834) ; [BOFiP BOI-BIC-CHAMP-40-20](https://bofip.impots.gouv.fr/bofip/3612-PGP.html) | golden D | référence précise à confirmer |
| RULE-LAND-NON-DEPRECIABLE-001 | 2025+ | Le terrain est séparé de la construction et n'est pas amorti. | [BOFiP BOI-BIC-AMT-10-20](https://bofip.impots.gouv.fr/bofip/2060-PGP.html) | propriété terrain | à revalider |
| RULE-FISCAL-VINTAGE-IMMUTABLE-001 | tous | Une règle historique n'est jamais modifiée : nouvelle version, empreinte et date d'effet. | politique de reproductibilité du projet | test millésime | interne |

## Incertitudes bloquantes ciblées

Qualification exacte LMNP/LMP selon situation du foyer, durée de report et ordre d'imputation des déficits, sort des amortissements en cas de cession/cessation, TVA/parahôtellerie, plus-values, frais d'acquisition, ventilation terrain/bâtiment, durées et composants, CFE et obligations annexes. Aucun taux, seuil, durée, case CERFA ni calcul correspondant n'est codé avant vérification sur les textes consolidés et formulaires du millésime.
