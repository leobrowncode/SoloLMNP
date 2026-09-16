# Déploiement et vérification des fondations

Cette phase fournit l'infrastructure de l'application. Elle ne permet pas encore de tenir
une comptabilité ni de produire une déclaration fiscale.

## Docker Compose

Prérequis : Docker Engine ou Docker Desktop avec Compose v2 récent, en mode conteneurs Linux.
Depuis la racine du dépôt :

```sh
docker compose up --build --wait
```

Ouvrir [SoloLMNP](http://127.0.0.1:5173). Le fichier `.env` est facultatif.
Le répertoire `data/` existe dans Git avec un marqueur vide ; la base est créée au
premier démarrage dans `data/sololmnp.sqlite3`. Le montage exige que le répertoire hôte
existe, pour éviter qu'un chemin erroné soit créé silencieusement par Docker.

| Service | Rôle | Réseau | Écriture autorisée |
| --- | --- | --- | --- |
| frontend | React compilé, servi par Nginx sans privilèges ; proxy `/api/` | `127.0.0.1:5173` → `8080` | `/tmp` éphémère |
| backend | FastAPI et migration Alembic au démarrage | `8000`, uniquement réseau Compose | `/app/data` persistant et `/tmp` éphémère |

Nginx conserve le chemin `/api/` et l'en-tête Host. Le navigateur utilise la même origine
pour l'interface et l'API ; aucune ouverture CORS n'est nécessaire. L'API n'est pas publiée
directement sur l'hôte. Les deux services s'exécutent avec un utilisateur non root, un système
de fichiers racine en lecture seule, toutes les capacités Linux retirées et l'élévation
de privilèges désactivée.

### Permissions Linux

L'utilisateur applicatif a par défaut les identifiants numériques `1000:1000`.
Sur Linux, ils doivent correspondre au propriétaire du répertoire `data/`.
Pour un compte différent, définir les valeurs retournées par `id -u` et `id -g`
dans `.env` avant la construction :

```dotenv
SOLOLMNP_UID=1001
SOLOLMNP_GID=1001
```

Ces nombres sont des exemples. Reconstruire ensuite avec `docker compose up --build --wait`.
Éviter un UID égal à zéro. Aucun service d'initialisation ne change les droits du système hôte.
Docker Desktop gère le partage du dossier Windows ; autoriser son partage si Docker le demande.

Pour déplacer les données, arrêter l'instance et transférer le dossier complet vers un
répertoire local existant, accessible en écriture, puis régler `SOLOLMNP_DATA_DIR`.
SQLite doit rester sur un disque local, pas sur un partage réseau.
Ne pas faire fonctionner deux instances sur la même base.

### Configuration

Copier `.env.example` vers `.env` permet de personnaliser Compose :

- `SOLOLMNP_PORT` : port local de l'interface, `5173` par défaut ;
- `SOLOLMNP_DATA_DIR` : répertoire de données hôte, `./data` par défaut ;
- `SOLOLMNP_UID` et `SOLOLMNP_GID` : utilisateur du conteneur backend ;
- `ALLOWED_HOSTS` : noms d'hôte acceptés par l'API, sans port.

Compose utilise volontairement des chemins internes fixes pour SQLite et les documents.
Les variables `DATABASE_URL` et `DOCUMENTS_DIR` de l'exemple servent au développement natif.
L'application ne possède pas d'authentification : l'auto-hébergement doit rester privé.
Un tunnel SSH vers le port local permet un accès distant sans publier directement le service.

### Démarrage, disponibilité et migrations

Le backend applique `python -m alembic upgrade head` avant Uvicorn, avec un masque de
création des fichiers `077`. Une migration échouée arrête le processus.

- `GET /api/health` vérifie que le processus répond ;
- `GET /api/status` vérifie la disponibilité, notamment le schéma SQLite attendu ;
- Compose attend la disponibilité du backend avant de démarrer le frontend ;
- `GET /healthz` vérifie le serveur de fichiers statiques Nginx.

L'API renvoie un statut HTTP 503 si le schéma attendu manque ; un processus vivant
ne suffit donc pas à déclarer l'application prête.

Avant une mise à jour, arrêter l'instance et sauvegarder tout `data/` ainsi que la
version de l'application et les paramètres locaux. Ne pas copier seulement le fichier
SQLite d'une instance en cours d'écriture : ses fichiers journal/WAL peuvent être nécessaires.
Le workflow applicatif de sauvegarde/restauration reste prévu à la phase 11.

```sh
docker compose logs --tail=100
docker compose down
```

L'arrêt et la suppression des conteneurs conservent le répertoire hôte `data/`.

## Développement natif

Installer Python 3.12 et Node.js 24. Depuis la racine du dépôt :

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e backend
Copy-Item .env.example .env
Push-Location backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
Pop-Location
```

### Linux

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e backend
cp .env.example .env
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Dans un second terminal, depuis la racine du dépôt :

```sh
cd frontend
npm ci
npm run dev
```

Vite écoute sur l'interface locale et transmet `/api/` à `127.0.0.1:8000`.
Les montants métier seront exprimés en Decimal côté Python ; aucune opération comptable
n'est introduite par les scripts de lancement.

## Vérifications reproductibles

Avec l'environnement Python activé et les dépendances frontend installées :

```sh
python scripts/check.py
```

Le script commun Windows/Linux lance le contrôle des dépendances Python, Ruff,
le contrôle du format, mypy, pytest, ESLint, TypeScript, Vitest et la compilation Vite.
Les options `--backend-only` et `--frontend-only` ciblent une seule partie.

Avec Docker disponible :

```sh
python scripts/docker_smoke.py
```

Ce test utilise un nom de projet unique, un port local temporaire et un dossier de données
temporaire distinct de `data/`. Il construit les images, vérifie la page et les endpoints,
les utilisateurs non root, la révision Alembic, puis insère une donnée SQLite fictive et
un document témoin. Il recrée les conteneurs et vérifie leur persistance avant de supprimer
uniquement son projet temporaire. Il se lance avec un utilisateur hôte non root.
Il ne faut pas transformer ce test en vérification sur une base personnelle.

La CI exécute :

1. les contrôles backend sous Ubuntu et Windows, avec Python 3.12 ;
2. l'audit des dépendances runtime Python sous Ubuntu ;
3. les contrôles frontend et l'audit npm sous Ubuntu, avec Node.js 24 ;
4. la validation Compose et le test Docker complet.

Les actions GitHub sont référencées par SHA de commit. Les paquets applicatifs sont
installés depuis les lockfiles ; les images de base utilisent des tags de version maintenue
(`python:3.12-slim-bookworm`, `node:24-alpine`, `nginxinc/nginx-unprivileged:1.28-alpine`).
Ces tags restent mutables : une reconstruction future peut recevoir des correctifs système.
La reproductibilité octet pour octet des images nécessitera le gel de leurs digests lors
d'une publication, avec une procédure régulière de mise à jour de sécurité.

**Limite de vérification de cette phase :** Docker n'est pas installé dans le poste de travail
ayant produit cette modification. Les vérifications Docker sont codées dans la CI ; leur
présence ne constitue pas la preuve qu'une exécution distante a réussi.

## Sources techniques consultées le 15 septembre 2026

- [Services Compose : santé, dépendances, montages et restrictions](https://docs.docker.com/reference/compose-file/services/)
- [Interpolation et valeurs par défaut de Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Image Nginx sans privilèges et chemins temporaires](https://github.com/nginx/docker-nginx-unprivileged)
- [Installation npm ci à partir du lockfile](https://docs.npmjs.com/cli/v11/commands/npm-ci/)
- [Configuration officielle de Node.js dans GitHub Actions](https://github.com/actions/setup-node)
