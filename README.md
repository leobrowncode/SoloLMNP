# SoloLMNP

Application libre, mono-utilisateur et auto-hébergeable pour une activité LMNP au réel simplifié BIC.

**Version 0.5.0 — comptabilité courante, immobilisations et états provisoires.** Sur `main` : ledger, opérations, banque, emprunts, registre des actifs, composants, dotations, inventaire manuel justifié, bilan et résultat provisoires par compte. La prévisualisation et la génération des à-nouveaux existent ; la génération exige un exercice source déjà clôturé, et le parcours de clôture n’est pas livré. Les états annuels réglementaires, le moteur fiscal, le FEC, la liasse et la sauvegarde applicative restent à développer. Cette version ne produit aucun montant déclarable.

## Démarrer

Avec Docker Desktop/Engine et Compose v2, en conteneurs Linux :

```sh
git clone https://github.com/leobrowncode/SoloLMNP.git
cd SoloLMNP
docker compose up --build --wait
```

Ouvrir [l'application locale](http://127.0.0.1:5173) depuis `main`. La base et les futurs documents restent dans `data/`. Le fichier `.env` est facultatif ; l'exemple permet de régler port et emplacement des données. Sur Linux, faire correspondre les UID/GID du backend au propriétaire de `data/` (voir le guide).

Le backend applique les migrations avant de démarrer. L'interface affiche l'état réel du service et du schéma SQLite. Une base absente, illisible ou non migrée ne sera pas déclarée prête.

**Dernière campagne enregistrée :** le 29 septembre 2026, le rapport de phase 5 indique 222 tests backend, 51 tests frontend, Ruff, mypy, ESLint, TypeScript et build Vite. Voir [le rapport de phase 5](docs/PHASE5_REPORT.md). Ces chiffres décrivent cette campagne ; ils ne remplacent pas une exécution nouvelle.

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
docs/         Modèles, règles, sécurité, déploiement, déclaration et roadmap
scripts/      Contrôles locaux, démarrage, Nginx et smoke Docker
data/         Données locales ignorées par Git
.github/      CI Linux/Windows, builds et suivi des phases
```

Flux métier : événements → comptabilité en partie double → états comptables → retraitements fiscaux versionnés → formulaires → saisie EFI manuelle. Le ledger est l'unique source du journal, grand livre, balance, bilan, résultat et, lorsqu'il existera, du FEC.

Les montants Python utilisent `Decimal`, avec stockage en centimes entiers SQLite. Toute valeur flottante, non finie ou fraction de centime est refusée à la frontière de stockage. Les couches fiscales ne doivent jamais altérer les écritures pour atteindre un résultat fiscal.

## Disponible et à venir

- Disponible : migrations jusqu'à `0005_opening`, activité unique, plusieurs biens, exercices, contraintes et tests d'intégrité.
- Disponible : écritures validées immuables, corrigées uniquement par extourne ; journal, grand livre et balance.
- Disponible : recettes et dépenses à l'engagement, règlements, banque CSV, rapprochement et emprunts ventilés.
- Disponible : immobilisations, terrain non amortissable, composants et dotations comptables.
- Disponible : inventaire manuel justifié, bilan et résultat provisoires par compte, prévisualisation des à-nouveaux.
- Limité : la génération des à-nouveaux exige une source clôturée. Le parcours de clôture n'existe pas encore.
- À venir : présentation réglementaire, clôture, fiscalité exécutable, FEC, liasse, documents archivés et sauvegarde applicative.
- Recherche : les scénarios A–J restent un catalogue ; les deux tests dits golden ne valident aucun résultat fiscal chiffré. Les millésimes fiscaux restent `research_only`.

Voir [le rapport de phase 1](docs/PHASE1_REPORT.md), [l'architecture](ARCHITECTURE.md), [la roadmap](ROADMAP.md), [le modèle de données](docs/DATA_MODEL.md), [la sécurité](SECURITY.md) et [le workflow EFI](docs/FILING.md).
