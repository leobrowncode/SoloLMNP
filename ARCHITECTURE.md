# Architecture

## Décisions

Monolithe modulaire : FastAPI/Pydantic/SQLAlchemy 2/Alembic, SQLite (WAL, foreign keys et transactions), React/TypeScript strict/Vite. Cette architecture limite les composants opérationnels, facilite sauvegarde et migration et préserve les frontières de domaine.

## Dépendances autorisées

`api → services → domain ← repositories`; `models` implémente la persistance, sans porter les règles. Les domaines accounting, banking, loans, assets, depreciation, fiscal, filing et documents ne communiquent que par identifiants et services applicatifs. Fiscal et filing lisent des vues immuables du ledger ; ils ne modifient jamais celui-ci.

## Invariants

1. Une écriture validée a au moins deux lignes, exactement un côté positif par ligne et débits = crédits.
2. Un exercice clôturé est immuable hors commande explicite de réouverture auditée.
3. Tout argent est `Decimal` quantifié ; SQLite stocke des unités mineures entières ou chaînes décimales contrôlées, jamais REAL.
4. Le terrain a une base amortissable nulle.
5. Les rapports et FEC sont des projections reproductibles d'écritures validées.
6. Les règles/mappings sont immuables par millésime et leur empreinte entre dans le snapshot.

## Déploiement

Deux conteneurs, bind-mount `data`, écoute loopback par défaut. Une instance = une activité et sa base ; aucune authentification n'est fournie, donc l'exposition Internet directe est interdite. Un reverse proxy privé avec TLS/authentification externe est requis si accès distant.


## Phase 2

Le module app.services.ledger orchestre la transaction de validation et les projections. app.api.ledger expose les opérations locales ; app.models.ledger porte la persistance. Le frontend features/LedgerPage.tsx fournit saisie et consultation. Les calculs monétaires du navigateur utilisent BigInt, les montants API sont des chaînes. Les migrations restent autonomes et figées.

## Phase 3

`app.services.operations` construit les écritures de recettes, dépenses, règlements et emprunts en réutilisant le service du ledger. Les modèles métier conservent le lien vers l'écriture validée, l'identité de retry et les métadonnées fiscales sans recalculer la comptabilité. L'import bancaire alimente un sous-ledger non comptable ; `bank_match` relie ensuite un mouvement à une ligne 512 unique. L'interface de `OperationsPage` impose une revue avant chaque mutation comptable. Voir [PHASE3_REPORT.md](docs/PHASE3_REPORT.md).

## Phase 4

Le domaine immobilisations ajoute un sous-ledger immuable `asset → composant → plan →
période`. La comptabilisation d'une période appelle le service ledger existant et ne
remplace jamais la dotation comptable par un montant fiscal. Les cumuls expliquent le
plan ; les états comptables futurs liront toujours les écritures validées. Voir
[PHASE4_REPORT.md](docs/PHASE4_REPORT.md).
