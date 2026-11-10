# AGENTS.md

## Contrat
- `SPEC.md` est le périmètre v1. Hors spec = refus. Léo est le seul arbitre.
- Ne pas modifier `fiscal/*/forms/` sans golden test qui prouve le changement.
- Réduire, ne pas réécrire : moteur fiscal, FEC, liasse, mappings 2025, plan de comptes, composants, emprunt.

## Stack v1
- Python 3.12, `lmnp_core` (calcul sans base), API FastAPI, CLI `python scripts/lmnp.py`.
- Dossier YAML + CSV. Blob privé Vercel en ligne. Auth Neon (`ALLOWED_EMAILS`). Legacy sous `/legacy`.
- Montants en centimes entiers. `AUTH_MODE=local` seulement hors production et hors Vercel.

## Commandes
- v1 : `python scripts/lmnp.py build <dossier>` et `serve` (127.0.0.1). Saisie : `scripts/start_v1.py` (`/v1`).
- En ligne : Vercel, `asgi.py`, `scripts/vercel_build.py`. Golden : `pytest lmnp_core/tests`. Legacy : `make check`.

## Carte
- `lmnp_core/` : dossier, fiscal, FEC, liasse, API, dépôt. `golden/`, `fiscal/`. `backend/` : moteur, auth, Blob. `frontend/` : `/v1` et `/legacy`.

## Conventions
- `lmnp_core` appelle le domaine pur, pas `app.services`. États : Brouillon, Vérifié, Déclaré. Pas de verrou `validation.json` sur v1.

## Messages de commit
- PR brouillon avant le premier push; objet `#<numero> <type>:`; corps `Nouvelles fonctionnalités produit :` ou `aucune` + `Technique :`. Voir `.cursor/rules/commits-numero-pr.mdc`.

## Pièges connus
- Cases 2025 depuis PDF archivés. `validation.json` : verrou legacy, ignoré en v1. JWT Neon : `iss`/`aud` sans `/neondb/auth`.
- Test Compta Demat : le validateur rejoue les règles, n'appelle pas l'outil Windows. Neon preview : 10 branches max.
- Importer `app.services` depuis `lmnp_core` est interdit.

## Méthode
- Lire `SPEC.md` et ce fichier; mettre à jour une ligne ici si besoin (max 40 lignes).
