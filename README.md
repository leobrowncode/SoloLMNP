# SoloLMNP

Application libre, mono-utilisateur et auto-hébergeable pour une activité LMNP au réel simplifié BIC.

**Version 0.2.0 — fondations techniques.** Le stockage, les migrations et l'écran de diagnostic sont implémentés. La saisie métier, le ledger persistant, les calculs fiscaux, le FEC et les déclarations restent à développer. Cette version ne produit aucun montant déclarable.

## Démarrer

Avec Docker Desktop/Engine et Compose v2, en conteneurs Linux :

```sh
git clone https://github.com/leobrowncode/SoloLMNP.git
cd SoloLMNP
docker compose up --build --wait
```

Pendant la revue, les fondations sont sur la branche `feat/foundation`, qui dépend de la PR de phase 0. Faire `git switch feat/foundation` avant de construire cette version.

Ouvrir [l'application locale](http://127.0.0.1:5173). La base et les futurs documents restent dans `data/`. Le fichier `.env` est facultatif ; l'exemple permet de régler port et emplacement des données. Sur Linux, faire correspondre les UID/GID du backend au propriétaire de `data/` (voir le guide).

Le backend applique les migrations avant de démarrer. L'interface affiche l'état réel du service et du schéma SQLite. Une base absente, illisible ou non migrée ne sera pas déclarée prête.

**Vérification actuelle :** tests natifs sous Windows et [CI complète réussie](https://github.com/leobrowncode/SoloLMNP/actions/runs/35065201132) : backend Linux/Windows, frontend et test Docker de construction, démarrage et persistance.

## Développement et contrôles

Python 3.12, Node.js 24 ; instructions PowerShell et Linux dans [DEPLOYMENT.md](docs/DEPLOYMENT.md).

```sh
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e backend
cd frontend
npm ci
cd ..
python scripts/check.py
```

Les fichiers `backend/requirements*.lock` et `frontend/package-lock.json` figent les dépendances. Les commandes sont à lancer dans un environnement Python isolé.

## Architecture

```text
backend/      FastAPI, configuration, SQLAlchemy, Alembic, contrats et tests
frontend/     React, TypeScript strict, diagnostic réel et tests d'interface
fiscal/       Recherches 2025/2026, statut research_only
docs/         Modèles, règles, sécurité, déploiement, déclaration et roadmap
scripts/      Contrôles locaux, démarrage, Nginx et smoke Docker
data/         Données locales ignorées par Git
.github/      CI Linux/Windows, builds et suivi des phases
```

Flux métier prévu : événements → comptabilité en partie double → états comptables → retraitements fiscaux versionnés → formulaires → saisie EFI manuelle. Le ledger sera l'unique source du journal, grand livre, balance, bilan, résultat et FEC.

Les montants Python utilisent `Decimal`, avec stockage en centimes entiers SQLite. Toute valeur flottante, non finie ou fraction de centime est refusée à la frontière de stockage. Les couches fiscales ne doivent jamais altérer les écritures pour atteindre un résultat fiscal.

## Disponible et à venir

- Disponible : migration `0001_foundation`, activité unique, plusieurs biens, exercices, contraintes et tests d'intégrité.
- Disponible : contrats d'écritures immuables avec validation d'équilibre ; aucun enregistrement comptable persistant.
- Disponible : API de santé/disponibilité, interface responsive, restrictions réseau et configuration.
- À venir : onboarding et API de saisie, ledger, opérations, actifs, états, fiscalité, clôture, FEC, liasse, documents et sauvegarde.
- Recherche : les scénarios A–J restent un catalogue ; les deux tests dits golden ne valident aucun résultat fiscal chiffré.

Voir [le rapport de phase 1](docs/PHASE1_REPORT.md), [l'architecture](ARCHITECTURE.md), [la roadmap](ROADMAP.md), [le modèle de données](docs/DATA_MODEL.md), [la sécurité](SECURITY.md) et [le workflow EFI](docs/FILING.md).
