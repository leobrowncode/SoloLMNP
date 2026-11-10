# Phase 1 — fondations

Date : 16 septembre 2026. Branche : `feat/foundation`, fondée sur la branche
de la PR de phase 0. Cette livraison prépare le ledger ; elle n'implémente
ni comptabilité persistante ni moteur fiscal.

## Ce qui est livré

- FastAPI avec fabrique d'application, configuration commune à l'API et Alembic,
  chemins indépendants du répertoire courant, listes Host/CORS explicites.
- SQLAlchemy 2 et SQLite : FK, WAL, synchronous FULL et transactions explicites.
- Migration réversible `0001_foundation` : activité unique, biens, exercices,
  clés étrangères, contraintes monétaires, états et cohérence des timestamps.
- Adaptateur monétaire Decimal ↔ centimes entiers, sans arrondi implicite,
  refus des valeurs flottantes, non finies, hors plage ou fractionnaires.
- Correction du contrat d'écriture hérité de P0 : données immuables, lignes
  copiées en tuple, statut non fourni au constructeur, validation retournant
  une nouvelle valeur équilibrée. Pas de ledger persistant à ce stade.
- Endpoints `/api/health` (vivacité) et `/api/status` (disponibilité réelle),
  statut 503 si base non migrée, corrompue ou version incompatible.
- Interface française responsive : chargement, état du stockage, erreurs,
  nouvelle tentative et périmètre réel des fonctionnalités.
- Versions verrouillées, images sans privilèges, proxy Nginx de même origine,
  montage des données locales, CI et script commun de vérification.
- Registre fiscal corrigé et disponibilité générale EFI documentée à partir
  des sources officielles ; définitions fiscales toujours `research_only`.
- Douze issues GitHub P1–P12 créées, avec critères d'acceptation.

## Versions principales vérifiées

| Composant | Version |
|---|---|
| Python exécuté | 3.12.14 |
| FastAPI | 0.141.1 |
| Pydantic / pydantic-settings | 2.13.5 / 2.15.0 |
| SQLAlchemy / Alembic | 2.0.54 / 1.20.0 |
| Uvicorn | 0.53.0 |
| Node.js exécuté | 24.11.0 |
| React / TypeScript | 19.3.0 / 5.9.3 |
| Vite / Vitest | 8.3.0 / 5.0.1 |

Les lockfiles font foi pour toutes les dépendances directes et transitives.
Les images Docker sont versionnées par tags maintenus, pas encore par digest.

## Vérification locale

- Installation depuis le lockfile Python et installation editable du package.
- `pip check`, Ruff, format Ruff et mypy strict : succès.
- Pytest : **95 tests réussis**, couverture mesurée **99 %** du code actuel.
  Deux avertissements de dépréciation Starlette/httpx restent visibles.
- Migrations : upgrade, idempotence, comparaison métadonnées, downgrade/upgrade.
- Intégrité : FK, contraintes SQLite, rollback DML et DDL, précision monétaire.
- ESLint, TypeScript strict, Vitest : **6 tests réussis**, build Vite réussi.
- Audits npm et pip-audit des dépendances runtime : aucune vulnérabilité connue
  signalée au moment de la vérification.
- Navigateur sur l'application locale avec vraie API/base migrée : disponibilité,
  actualisation et affichage mobile à 390 px contrôlés, sans débordement horizontal.
- `git diff --check` et inspection des fichiers suivis avant commit.

## Validation distante

La [CI #4](https://github.com/leobrowncode/SoloLMNP/actions/runs/35065201132)
est intégralement réussie sur le commit `b565296` :
backend Ubuntu, backend Windows, frontend et Docker. Le job Docker a construit
les images et vérifié démarrage, migrations, disponibilité HTTP, utilisateurs
non root et persistance après recréation. Cette vérification complète les tests
locaux. La PR #14 reste en brouillon pour revue, dépendante de la PR #1.

## Limites

Docker n'est pas installé sur le poste de développement. Le smoke CI construit
les deux images, vérifie HTTP, migrations, utilisateurs non root et persistance
après recréation des conteneurs ; cette exécution distante a maintenant réussi.

Les tables administratives n'ont pas encore d'API de saisie. Le workflow de
clôture, le verrouillage des exercices, l'audit et les validations métier
restent dans leurs phases respectives. Aucun contrôle fiscal ni financier
opérationnel n'est annoncé sur la base de cette migration.

Les scénarios A–J existants sont des spécifications, pas des golden tests
fiscaux chiffrés. Les futurs résultats seront figés après vérification des
règles officielles, des périodes d'effet et des formulaires applicables.

## Prochaine phase

P2 : persistance Account / AccountingJournal / AccountingEntry /
AccountingEntryLine ; validation atomique débit/crédit, chronologie,
numérotation, journal, grand livre, balance et tests d'invariants.
