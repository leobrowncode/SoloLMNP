# Roadmap

- **P0 Recherche/architecture (présent)** : squelettes, invariants, menaces, modèles, registre de sources, fixtures et contrats.
- **P1 Fondations** : modèles SQLAlchemy/migration initiale, configuration SQLite, API, UI shell, dépendances verrouillées, CI durcie.
- **P2 Ledger** : plan configurable, journaux, écritures/lignes, validation atomique, journal/grand livre/balance et property tests.
- **P3 Opérations** : recettes/dépenses, CSV bancaire idempotent, rapprochement, emprunts ventilés.
- **P4 Immobilisations** : registre/composants, terrain, plans et écritures d'amortissement comptable.
- **P5 États** : inventaire, bilan/résultat issus du ledger, à-nouveaux et continuité.
- **P6 Fiscal** : règles sourcées par millésime, retraitements, deux registres de reports, golden tests.
- **P7 Clôture/audit** : validations, audit append-only, verrouillage/réouverture/invalidation.
- **P8 FEC** : recherche actualisée, exporter/validator et fixtures officielles.
- **P9 Liasse** : définitions officielles 2031/2033, DSL/mappings, contrôles, package/snapshot.
- **P10 EFI** : déclaration, mode double-écran, rapport PDF, feuille, données 2042-C-PRO.
- **P11 Documents/backup** : uploads durcis, associations, sauvegarde/restauration/exports.
- **P12 Hardening** : E2E, sécurité, accessibilité, performance, migration et documentation opérateur.

## Backlog GitHub

Les fichiers de corps reproductibles sont dans `.github/ISSUES.md`. La création distante nécessite un remote et une authentification GitHub ; elle doit être exécutée avec `gh issue create` dès qu'ils existent.
