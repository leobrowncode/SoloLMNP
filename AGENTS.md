# AGENTS.md
## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, SQLite (local) ou Postgres via `DATABASE_URL`.
- Frontend: React 19, TypeScript strict, Vite, Vitest.
- Déploiement: Vercel (`asgi.py`, `vercel.json`), Docker Compose, lanceur `scripts/start_local.py`.
- E2E: Playwright dans `e2e/` (hors `scripts/check.py`).

## Commandes
- Dev local: `python scripts/start_local.py` (ou `./scripts/start_local.sh`, `SoloLMNP.bat`, `docker compose up --build --wait`).
- Contrôle complet: `python scripts/check.py` ou `make check` (Ruff, mypy, pytest, ESLint, tsc, Vitest, build Vite).
- Ciblées: `make test|lint|typecheck|build` ; migration seule: `make migrate` (`alembic upgrade head` dans `backend/`).
- Frontend seul (dev): `cd frontend && npm run dev`.
- Parcours navigateur: `cd e2e && npm ci && npm test` (API réelle).

## Carte par dossier
- `backend/`: API FastAPI (`app/`: api, services, domain, models, repositories), migrations Alembic, tests pytest.
- `frontend/`: SPA React (`src/features/`, `src/api/`, jetons `tokens.css`).
- `fiscal/`: règles et formulaires par millésime (statut recherche, voir `validation.json`).
- `docs/`: modèle, déploiement, règles fiscales, tutoriel, rapports de phase.
- `scripts/`: lanceur, `check.py`, build Vercel, smoke Docker.
- `e2e/`: tests Playwright.
- Racine: `asgi.py`, `docker-compose.yml`, `data/` (données locales ignorées par Git), `.github/workflows/ci.yml`.

## Conventions
- Dépendances backend: `api → services → domain ← repositories` ; le fiscal ne modifie pas le ledger.
- Montants: `Decimal` côté Python, centimes entiers en base ; refus des flottants à la persistance.
- CI sur `main` et PR: backend Linux/Windows, Postgres, frontend, e2e, docker smoke (`Makefile` reprend les commandes).

## Messages de commit
- PR brouillon avant le premier push; objet `#<numero> <type>:`; corps `Nouvelles fonctionnalités produit :` ou `aucune` + `Technique :`. Voir `.cursor/rules/commits-numero-pr.mdc`.

## Pièges connus
- Millésimes 2025/2026 en **Recherche** tant que `fiscal/<année>/validation.json` n'est pas une attestation effective.
- `scripts/check.py` n'exécute pas Playwright; l'e2e est manuel ou job CI dédié.
- Migrations: au démarrage local/Docker; sur Vercel via `scripts/vercel_build.py` au build.
- Après Google, le Bearer vient de `set-auth-jwt` ou de `GET /token` (pas `session.token`). Le JWT Neon a `iss` et `aud` égaux à l’origine de `NEON_AUTH_BASE_URL`, sans le chemin `/neondb/auth`.

## Méthode de travail
- Lire ce fichier, recherche ciblée (grep, chemins ci-dessus); en fin de tâche, une ligne de mise à jour ici (max 40 lignes).
