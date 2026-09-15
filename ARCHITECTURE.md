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
