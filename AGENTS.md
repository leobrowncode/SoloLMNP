# AGENTS.md

## Contrat
- `SPEC.md` est le périmètre v1. Hors spec = refus. Léo est le seul arbitre.
- Ne pas modifier `fiscal/*/forms/` sans golden test qui prouve le changement.
- Réduire, ne pas réécrire : moteur fiscal, FEC, liasse, mappings 2025, plan de comptes, composants, emprunt.

## Stack v1
- Python 3.12, paquet `lmnp_core` (calcul sans base), API FastAPI, CLI `python scripts/lmnp.py`.
- Dossier YAML + CSV + justificatifs. Fichiers locaux, ou Blob privé sur Vercel (un dossier par owner).
- Auth : Neon Auth en ligne (`ALLOWED_EMAILS`). `AUTH_MODE=local` sans secret, refusé si `APP_ENV=production` ou `VERCEL=1`.
- Montants en centimes entiers. Le legacy (SQLAlchemy, Postgres) reste sous `/legacy`.

## Commandes
- v1 : `python scripts/lmnp.py build <dossier>` et `serve` (127.0.0.1).
- Saisie : `python scripts/start_v1.py` (local, zéro secret, `/v1`).
- En ligne : Vercel, `asgi.py`, `scripts/vercel_build.py`.
- Golden : `python -m pytest lmnp_core/tests` (PYTHONPATH : racine et `backend/`). Job CI `Noyau v1`.
- Legacy : `python scripts/check.py`, `make check`.

## Carte
- `lmnp_core/` : dossier, écritures, fiscal, FEC, liasse, 2042, état de suivi, API, dépôt.
- `golden/` : dossiers de référence. `fiscal/` : règles et formulaires. 2027 hors v1.
- `backend/` : moteur réutilisé, auth Neon, client Blob. `frontend/` : UI v1 (`/v1`) et legacy (`/legacy`).
- `docs/archive/` : rapports de phase.

## Conventions
- `lmnp_core` appelle le domaine pur (`app.domain.fiscal.engine`, FEC, liasse, plan). Pas `app.services`.
- États : Brouillon, Vérifié par l'utilisateur, Déclaré. Pas de verrou `validation.json` sur le chemin v1.

## Pièges connus
- Les cases 2025 viennent des PDF archivés. Ne pas recopier un numéro de 2026 ou 2027.
- `validation.json` décrit l'ancien verrou Recherche. La v1 ne le consulte pas.
- JWT Neon : `iss` et `aud` sont l'origine de `NEON_AUTH_BASE_URL`, sans `/neondb/auth`. Le validateur FEC ne lance pas Test Compta Demat.
- Aperçu Vercel : le plan Neon gratuit plafonne à 10 branches `preview/<branche>`. Ne pas en supprimer.

## Méthode
- Lire `SPEC.md` et ce fichier, puis chercher un chemin ciblé.
- Si une commande ou un dossier change, mettre à jour une ligne ici. Rester sous 40 lignes.
