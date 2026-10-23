# SoloLMNP

Application libre, mono-utilisateur et auto-hébergeable pour une activité LMNP au réel simplifié BIC.

**Version 1.0.0 — comptabilité LMNP de l’exercice 2026.** Le ledger, les opérations, la banque, les emprunts, l’entrée du bien au premier exercice, les immobilisations, les états, la clôture, la liasse à recopier (2031, 2031-bis, 2033-A/B/C/E, cases 2042-C-PRO, état de suivi des amortissements non déduits) et le dossier de contrôle (FEC `SirenFECAAAAMMJJ` + description + empreintes) sont disponibles. SoloLMNP n’envoie rien : la liasse se recopie en mode EFI sur impots.gouv.fr. Le LMP, la cession, la TVA et les plus-values restent hors périmètre.

## Démarrer

Prérequis locaux : Python 3.12+ et Node.js 24. Puis, depuis la racine du dépôt :

- **Windows :** double-cliquer sur [`SoloLMNP.bat`](SoloLMNP.bat)
- **Linux / macOS :** `./scripts/start_local.sh`
- **Tous systèmes :** `python scripts/start_local.py`

Le lanceur crée `.venv` et installe les dépendances au besoin, migre SQLite, démarre API + interface, puis ouvre [http://127.0.0.1:5173](http://127.0.0.1:5173). Les données restent dans `data/`. Tutoriel d’usage : [docs/TUTORIAL.md](docs/TUTORIAL.md).

Alternative Docker (Compose v2, conteneurs Linux) :

```sh
docker compose up --build --wait
```

Sur Linux avec Docker, faire correspondre les UID/GID du backend au propriétaire de `data/` (voir [DEPLOYMENT.md](docs/DEPLOYMENT.md)). Le fichier `.env` est facultatif.

Le backend applique les migrations avant de démarrer. L’interface affiche l’état réel du service et du schéma SQLite. Une base absente, illisible ou non migrée ne sera pas déclarée prête.

**Vérification locale :** `python scripts/check.py` (Ruff, mypy, pytest, ESLint, TypeScript, Vitest, build). Les rapports [P5](docs/PHASE5_REPORT.md) à [P12](docs/PHASE12_REPORT.md) décrivent le périmètre et les limites. La CI distante n’a pas été relancée.

**Historique P1 :** tests natifs sous Windows et [CI complète réussie](https://github.com/leobrowncode/SoloLMNP/actions/runs/35065201132) : backend Linux/Windows, frontend et test Docker de construction, démarrage et persistance.

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
docs/         Modèles, règles, sécurité, déploiement, tutoriel et roadmap
scripts/      Contrôles locaux, lanceur natif, Nginx et smoke Docker
SoloLMNP.bat  Lanceur Windows (double-clic)
data/         Données locales ignorées par Git
.github/      CI Linux/Windows, builds et suivi des phases
```

Flux métier prévu : événements → comptabilité en partie double → états comptables → retraitements fiscaux versionnés → formulaires → saisie EFI manuelle. Le ledger sera l'unique source du journal, grand livre, balance, bilan, résultat et FEC.

Les montants Python utilisent `Decimal`, avec stockage en centimes entiers SQLite. Toute valeur flottante, non finie ou fraction de centime est refusée à la frontière de stockage. Les couches fiscales ne doivent jamais altérer les écritures pour atteindre un résultat fiscal.

## Disponible et à venir

- Disponible : migration `0001_foundation`, activité unique, plusieurs biens, exercices, contraintes et tests d'intégrité.
- Disponible : contrats d'écritures immuables avec validation d'équilibre ; aucun enregistrement comptable persistant.
- Disponible : API de santé/disponibilité, interface responsive, restrictions réseau et configuration.
- Disponible : ledger, opérations, banque CSV, import CSV de justificatifs, emprunts, immobilisations, états provisoires, centralisation, clôture, FEC, mappings de travail, feuille EFI, justificatifs et sauvegarde.
- Recherche : le calcul fiscal enregistré reste `research_only`, parce que le LMP, la cession, la TVA et les plus-values sont hors périmètre. La feuille de l’exercice 2026 est recopiable si chaque case est au registre lu et qu’aucun écart ne bloque.

Voir [le rapport de phase 1](docs/PHASE1_REPORT.md), [l'architecture](ARCHITECTURE.md), [la roadmap](ROADMAP.md), [le modèle de données](docs/DATA_MODEL.md), [la sécurité](SECURITY.md) et [le workflow EFI](docs/FILING.md).
