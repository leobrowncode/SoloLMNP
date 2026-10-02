# Formulaires et mappings

## Inventaire prudent

La déclaration de résultat industrielle et commerciale utilise la série 2031 et, sous réel simplifié, la liasse simplifiée 2033 (notamment A bilan, B résultat, C immobilisations/amortissements, D déficits/provisions, E valeur ajoutée, F composition du capital, G filiales/participations), seulement lorsque le formulaire et la situation du millésime les rendent applicables. Sources à récupérer par millésime dans le [moteur de recherche des formulaires DGFiP](https://www.impots.gouv.fr/formulaire) et la [fiche 2031-SD](https://www.impots.gouv.fr/formulaire/2031-sd/impot-sur-le-revenu-benefices-industriels-et-commerciaux).

Les fichiers `fiscal/{année}/forms/2033.json` sont une structure de travail `research_only`. Ils ne recopient pas les cases CERFA. Les notices officielles doivent encore être archivées par URL et empreinte avant tout montant déclarable. La 2042-C-PRO reste un produit séparé : `official_case` est nul et le statut est `case_not_verified`.

## Mapping

Une définition YAML versionnée contient formulaire, millésime, version, sources, champs, type, obligation et formule déclarative. Le compilateur accepte seulement un DSL en liste blanche (`sum_accounts`, `balance`, `tax_result`, additions/soustractions), jamais `eval`. Chaque `TaxFormFieldResult` conserve expression, Rule IDs, comptes et écritures sources, statut et contrôles. Les contrôles inter-formulaires forment un graphe explicite ; une dépendance ou case obligatoire manquante bloque READY.
