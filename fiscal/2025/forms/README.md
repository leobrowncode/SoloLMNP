# Formulaires 2025

Sources officielles archivées le 2 octobre 2026 : voir [`../sources/manifest.json`](../sources/manifest.json)
et le registre des cases [`cases.yaml`](cases.yaml).

`2033.json` reste le fichier de formules du 2033-B (`research_only` comme format
de travail). Le statut affiché (Recherche, Provisoire, Déclarable) est décidé
par `../validation.json` et les portes du package, pas par ce fichier.
Chaque champ du 2033-B porte un `official_case` vérifié sur la liasse 2025.
Aucun millésime n’est déclarable tant que `validation.json` reste `research_only`.

Règles dures avant une feuille complète :

- refuser toute case déclarable avec `official_case = null` ou `verification = case_not_verified` ;
- ne pas copier les identifiants d’un autre millésime ;
- 2033-F / 2033-G : non applicables aux entreprises individuelles (notice) ;
- 2042-C-PRO : produit séparé, hors archive de ce lot.
