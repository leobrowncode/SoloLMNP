# Formulaires et mappings

## Inventaire prudent

La déclaration de résultat industrielle et commerciale utilise la série 2031 et, sous réel simplifié, la liasse simplifiée 2033 (notamment A bilan, B résultat, C immobilisations/amortissements, D déficits/provisions, E valeur ajoutée, F composition du capital, G filiales/participations), seulement lorsque le formulaire et la situation du millésime les rendent applicables. Sources : [moteur de recherche des formulaires DGFiP](https://www.impots.gouv.fr/formulaire) et [fiche 2031-SD](https://www.impots.gouv.fr/formulaire/2031-sd/impot-sur-le-revenu).

## Millésime 2025 — sources archivées

Le **2 octobre 2026**, les PDF officiels suivants ont été téléchargés et empreintés dans
[`fiscal/2025/sources/`](../fiscal/2025/sources/) :

| Document | CERFA | Empreinte |
|---|---|---|
| 2031-SD | 11085*27 | `ac642cc3…f758` |
| Liasse 2033-A à G | 15948*07 | `264c870d…758b` |
| Notice 2033-NOT-SD | 50448*27 | `6bcda8ac…291b` |

Le registre [`fiscal/2025/forms/cases.yaml`](../fiscal/2025/forms/cases.yaml) mappe chaque case MVP
vers une source vérifiée. Les entreprises individuelles n’ont pas à servir 2033-F ni 2033-G
(notice). La 2042-C-PRO est un produit séparé. Revenus 2025 : CERFA 11222*28 archivé, cases 5NA / 5NY vérifiées, 5NK et 5NZ bloquées. Millésime projet 2026 : `case_not_verified`.

`fiscal/2025/forms/2033.json` porte les formules du 2033-B. Le registre
`cases.yaml` dit si les contrôles internes de la feuille sont satisfaits. Le
passage à Déclarable est ailleurs : `fiscal/<millésime>/validation.json`
(source officielle, date, périmètre, version). Voir
[FISCAL_RULES.md](FISCAL_RULES.md). Le calcul stocké reste `research_only`.
Les millésimes 2025 et 2026 ne sont pas déclarables.

## Mapping

Une définition YAML versionnée contient formulaire, millésime, version, sources, champs, type, obligation et formule déclarative. Le compilateur accepte seulement un DSL en liste blanche (`sum_accounts`, `balance`, `tax_result`, additions/soustractions), jamais `eval`. Chaque `TaxFormFieldResult` conserve expression, Rule IDs, comptes et écritures sources, statut et contrôles. Les contrôles inter-formulaires forment un graphe explicite ; une dépendance ou case obligatoire manquante, ou une case `official_case = null` / `case_not_verified` sur le chemin BIC, bloque READY.
