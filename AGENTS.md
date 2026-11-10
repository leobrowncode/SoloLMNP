# AGENTS.md

## Contrat
- `SPEC.md` est le périmètre v1. Hors spec = refus. Léo est le seul arbitre.
- Ne pas modifier `fiscal/*/forms/` sans golden test qui prouve le changement.
- Réduire, ne pas réécrire : moteur fiscal, FEC, liasse, mappings 2025, plan de comptes, composants, emprunt.

## Stack v1
- Python 3.12, paquet `lmnp_core` (sans base ni HTTP au cœur), API FastAPI fine, CLI `python scripts/lmnp.py`.
- Données : un dossier YAML + CSV. Montants en centimes entiers. Aucun secret.
- Le dépôt legacy (SQLAlchemy, React, auth, Postgres, Vercel) reste sous le tag `v0-archive`. Il n'est pas le chemin v1.

## Commandes
- v1 : `python scripts/lmnp.py build <dossier>` et `python scripts/lmnp.py serve` (127.0.0.1, zéro secret).
- Golden : `python -m pytest lmnp_core/tests` (PYTHONPATH : racine et `backend/`).
- Legacy, hors chemin v1 : `python scripts/check.py`, `make check`.

## Carte
- `lmnp_core/` : dossier, écritures, fiscal, FEC, liasse, 2042, état de suivi, API.
- `golden/` : dossiers de référence `input/` + `expected.json`.
- `fiscal/` : règles et formulaires par millésime. 2027 hors v1.
- `backend/` : moteur et mappings réutilisés. `frontend/` : UI legacy, saisie v1 au jalon suivant.
- `docs/archive/` : rapports de phase, audits, `AGENT_STATE.md`.

## Conventions
- Dépendances v1 : `lmnp_core` appelle le domaine pur (`app.domain.fiscal.engine`, FEC, liasse, plan).
- États de sortie : Brouillon, Vérifié par l'utilisateur, Déclaré. Pas de verrou `validation.json` sur le chemin v1.
- Trois états seulement. L'outil calcule, l'utilisateur signe.

## Pièges connus
- Les cases 2025 viennent des PDF archivés. Ne pas recopier un numéro de 2026 ou 2027.
- `validation.json` décrit encore l'ancien verrou Recherche du legacy. La v1 ne le consulte pas.
- Test Compta Demat est un outil Windows : le validateur du dépôt rejoue les règles publiées, il ne lance pas l'outil.
- Importer `app.services` depuis `lmnp_core` est interdit : ces services parlent à la base.

## Méthode
- Lire `SPEC.md` et ce fichier, puis chercher un chemin ciblé.
- Si une commande ou un dossier change, mettre à jour une ligne ici. Rester sous 40 lignes.
