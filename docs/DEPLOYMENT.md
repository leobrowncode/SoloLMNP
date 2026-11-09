# Déploiement

Installation locale ou Docker. Les millésimes chargés restent en recherche : l’application
prépare une comptabilité et une feuille à contrôler, elle ne produit pas une déclaration fiable.

## Lanceur local (sans Docker)

Prérequis : Python 3.12+ et Node.js 24 avec `npm`.

| Système | Commande |
| --- | --- |
| Windows | Double-cliquer sur `SoloLMNP.bat` |
| Linux / macOS | `./scripts/start_local.sh` |
| Tous | `python scripts/start_local.py` |

Le script `scripts/start_local.py` crée `.venv`, installe `backend/requirements.lock` et les
dépendances frontend si besoin, copie `.env.example` vers `.env`, applique les migrations,
démarre Uvicorn (`127.0.0.1:8000`) et Vite (`127.0.0.1:5173`), puis ouvre le navigateur.
Arrêt avec Ctrl+C. Guide métier : [TUTORIAL.md](TUTORIAL.md). Cycle d’un exercice :
[ANNUAL_CYCLE.md](ANNUAL_CYCLE.md). Limites : [LIMITS.md](LIMITS.md).

Le fichier copié depuis `.env.example` active le dossier local : `APP_ENV=development`,
`AUTH_MODE=local`, `VITE_AUTH_MODE=local`. Aucun secret Neon n’est demandé. L’API traite
chaque requête comme le compte fixe `sololmnp-local` (le premier compte, `owner_id` 1 sur
une base neuve). Ce mode est refusé si `APP_ENV` vaut `production` ou si `VERCEL=1` :
l’application ne démarre pas. Un `.env` déjà présent n’est pas réécrit. Pour le même
comportement, y ajouter ces trois variables, puis relancer.

Le parcours navigateur n’utilise pas `data/`. Depuis `e2e/`, après `npm ci` et
`npx playwright install chromium`, `npm test` démarre l’API sur une base temporaire
et Vite. Il faut le Python du dépôt (dépendances backend installées).

## Docker Compose

Prérequis : Docker Engine ou Docker Desktop avec Compose v2 récent, en mode conteneurs Linux.
Depuis la racine du dépôt :

```sh
docker compose up --build --wait
```

Ouvrir [SoloLMNP](http://127.0.0.1:5173). Le fichier `.env` est facultatif.
Sans variable, Compose prend `APP_ENV=development` et `AUTH_MODE=local`, et construit
l’interface avec `VITE_AUTH_MODE=local`. Le dossier s’ouvre sans secret Neon.
`APP_ENV=production` avec `AUTH_MODE=local` fait échouer le démarrage du backend.
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
Un chemin de base qui contient « OneDrive » fait renvoyer `storage_warning` par `GET /api/status`. L’interface affiche alors l’alerte « Stockage non sûr » sur chaque vue, y compris lorsque la base est prête. Copiez le projet hors du dossier synchronisé : la synchronisation peut corrompre SQLite.
Ne pas faire fonctionner deux instances sur la même base.

### Configuration

Copier `.env.example` vers `.env` permet de personnaliser Compose :

- `SOLOLMNP_PORT` : port local de l'interface, `5173` par défaut ;
- `SOLOLMNP_DATA_DIR` : répertoire de données hôte, `./data` par défaut ;
- `SOLOLMNP_UID` et `SOLOLMNP_GID` : utilisateur du conteneur backend ;
- `ALLOWED_HOSTS` : noms d'hôte acceptés par l'API, sans port.

Compose utilise volontairement des chemins internes fixes pour SQLite et les documents.
Les variables `DATABASE_URL` et `DOCUMENTS_DIR` de l'exemple servent au développement natif.
En mode local, les routes `/api/*` autres que `GET /api/health` utilisent le compte fixe,
sans JWT. Dès que `AUTH_MODE` vaut `neon`, le navigateur envoie `Authorization: Bearer`
après une connexion Neon Auth (e-mail ou Google), et `ALLOWED_EMAILS` refuse toute autre
adresse. Les variables sont dans `.env.example`.
`VITE_NEON_AUTH_URL` et `VITE_AUTH_MODE` sont figés dans l’image frontend : la reconstruire
après un changement.
Elle est aussi ajoutée à `connect-src`, avec `https://vercel.com` pour le dépôt direct des fichiers de plus de 3 Mio.
L’écoute reste sur `127.0.0.1` : un tunnel SSH suffit pour un accès distant.

### Démarrage, disponibilité et migrations

Le backend applique `python -m alembic upgrade head` avant Uvicorn, avec un masque de
création des fichiers `077`. Une migration échouée arrête le processus.

- `GET /api/health` vérifie que le processus répond, sans session ;
- `GET /api/status` vérifie la disponibilité, notamment le schéma attendu, et exige une session ;
- Compose attend la disponibilité du backend avant de démarrer le frontend ;
- `GET /healthz` vérifie le serveur de fichiers statiques Nginx.

L'API renvoie un statut HTTP 503 si le schéma attendu manque ; un processus vivant
ne suffit donc pas à déclarer l'application prête.

Avant une mise à jour, arrêter l'instance et sauvegarder tout `data/` ainsi que la
version de l'application et les paramètres locaux. Ne pas copier seulement le fichier
SQLite d'une instance en cours d'écriture : ses fichiers journal/WAL peuvent être nécessaires.
La sauvegarde et la restauration applicatives sont décrites dans [BACKUP.md](BACKUP.md). Une restauration confirmée prend d’abord une copie de l’état actuel. Avec `BLOB_READ_WRITE_TOKEN`, les justificatifs et les archives de dossier vont dans un magasin Vercel Blob privé ; sans jeton, ils restent sur le disque.

```sh
docker compose logs --tail=100
docker compose down
```

L'arrêt et la suppression des conteneurs conservent le répertoire hôte `data/`.

## Vercel

Un projet, racine du dépôt (ni `frontend/` ni `backend/`). Le framework est FastAPI, déjà déclaré dans `vercel.json`. L’interface est le build Vite. L’API est la fonction `asgi.py`, sous `/api`, sur la même origine : pas de CORS en production. Ne pas définir `outputDirectory`, et ne pas ajouter de réécriture qui enverrait `/api` vers `index.html`.

Le lanceur local et Docker ne passent pas par ce build. Ils migrent au démarrage du processus, sur SQLite, comme avant.

### Déjà fixé dans le dépôt

- Python 3.12 (`.python-version`) et Node 24 (`.node-version`).
- `functions.asgi.py.maxDuration` : 300 secondes. La mémoire ne se règle pas dans `vercel.json`. Sur un plan Pro, choisir Performance (4 Go, 2 vCPU) dans le tableau de bord. Hobby reste à 2 Go et 1 vCPU. Si une archive expire encore, monter `maxDuration` jusqu’à 800 sur Pro.
- `scripts/vercel_build.py` construit le frontend, puis lance `alembic upgrade head` seulement quand `VERCEL=1` et `VERCEL_ENV` vaut `preview` ou `production`. Ailleurs, il ne migre pas.
- La migration utilise `DATABASE_URL_UNPOOLED` (hôte direct, sans `-pooler`). Le verrou `pg_advisory_lock` dure le temps du build, avec un `lock_timeout` de 180 secondes. Deux déploiements ne migrent pas ensemble. Un échec fait échouer le build : le déploiement précédent reste en service.
- Une preview refuse la migration si `SOLOLMNP_PRODUCTION_DB_HOST` manque, ou si l’hôte direct visé est celui de la production. La variable est le nom d’hôte, sans utilisateur ni mot de passe.
- `APP_ENV=production` est exigé. `AUTH_MODE` autre que `neon`, et `VITE_AUTH_MODE` autre que vide ou `neon`, sont refusés. `AUTH_MODE=test` et `AUTH_MODE=local` le sont aussi dès que `VERCEL=1`, y compris si `APP_ENV` n’est pas `production`.
- Les hôtes `VERCEL_URL`, `VERCEL_BRANCH_URL` et `VERCEL_PROJECT_PRODUCTION_URL` sont acceptés. Un domaine propre se déclare dans `ALLOWED_HOSTS`.
- `VERCEL_FASTAPI_STATIC_CDN=1` et `tool.vercel.fastapi.static.cdn = true` envoient le build Vite vers le CDN. Sans la variable, les fichiers restent dans la fonction.
- La CSP du navigateur est une balise injectée au build. `connect-src` contient l’origine de `VITE_NEON_AUTH_URL` et `https://vercel.com`. L’en-tête HTTP ne contient que `frame-ancestors 'none'` : un second `connect-src` plus étroit bloquerait Neon Auth.

### Projet Neon

1. Créer le projet dans la même région que la fonction Vercel.
2. Activer Neon Auth (Better Auth géré) sur la branche de production, qui est aussi la branche par défaut.
3. Noter l’hôte direct de production : le nom d’hôte sans `-pooler`, sans utilisateur et sans mot de passe.

### Projet Vercel

1. Importer `leobrowncode/SoloLMNP`.
2. Racine du dépôt. Framework FastAPI, lu depuis `vercel.json`.
3. Node.js 24.x, Python 3.12.
4. Branche de production `main`. Previews activées pour les pull requests.
5. Région de la fonction égale à la région Neon.

### Intégration Neon–Vercel

Ne pas poser `DATABASE_URL` avant de connecter l’intégration : la liaison échoue si la variable existe déjà.

1. Console Neon, Integrations, Vercel, lier le compte existant.
2. Intégration gérée par Neon. Un projet Neon pour un projet Vercel. Ne pas activer en même temps l’intégration gérée par Vercel.
3. Choisir la branche de production : pas un nom `preview/*`, pas de TTL.
4. Activer la suppression automatique des branches de preview devenues inutiles.
5. La branche `vercel-dev` est facultative.
6. Laisser l’intégration injecter `DATABASE_URL` (hôte `-pooler`), `DATABASE_URL_UNPOOLED` (hôte direct), `NEON_AUTH_BASE_URL` et `VITE_NEON_AUTH_URL`.
7. Chaque pull request reçoit une branche Neon `preview/<branche-git>`, avec sa base et son URL d’auth. Ne jamais faire pointer le `DATABASE_URL` d’une preview vers la production.
8. Cette branche de preview est créée depuis la branche par défaut du projet Neon, même si la production Vercel utilise une autre branche.

`NEON_AUTH_JWKS_URL` n’est pas injectée. Vide, l’API prend `{NEON_AUTH_BASE_URL}/.well-known/jwks.json`.

### Variables

Production et Preview :

| Variable | Rôle |
| --- | --- |
| `DATABASE_URL` | Injectée. Hôte `-pooler`. Exécution de l’API seulement. |
| `DATABASE_URL_UNPOOLED` | Injectée. Hôte direct. Migrations Alembic seulement. |
| `NEON_AUTH_BASE_URL` | URL Auth en https. La même que la ligne suivante. |
| `VITE_NEON_AUTH_URL` | La même URL. Elle est lue au build : redéployer après un changement. |
| `NEON_AUTH_JWKS_URL` | Facultative. |
| `BLOB_READ_WRITE_TOKEN` | Sensible. Magasin Blob privé. |
| `ALLOWED_EMAILS` | Adresses autorisées, séparées par des virgules. |
| `APP_ENV` | `production`. |
| `AUTH_MODE` | Absente, ou `neon`. Jamais `test`, jamais `local`. |
| `VITE_AUTH_MODE` | Absente, ou `neon`. Jamais `local`. |
| `VERCEL_FASTAPI_STATIC_CDN` | `1`. |
| `ALLOWED_HOSTS` | Domaine propre, et le host `vercel.app` de production s’il est utilisé. |

Preview seulement :

| Variable | Rôle |
| --- | --- |
| `SOLOLMNP_PRODUCTION_DB_HOST` | Hôte direct de production, sans mot de passe. Absent ou égal à la cible : le build échoue. |

Développement local : ne pas définir ces variables Vercel. SQLite, `python scripts/start_local.py` et Compose restent la voie locale, avec `AUTH_MODE=local`. Pour un essai contre une branche Neon, passer `AUTH_MODE=neon`, les trois URL d’auth et `ALLOWED_EMAILS`, puis reconstruire l’image frontend si Docker est utilisé.

### Blob, fichiers de plus de 3 Mio

Le magasin est privé. Au-delà de 3 Mio, le navigateur envoie le fichier en PUT vers `https://vercel.com/api/blob`. Le magasin doit autoriser l’origine de l’application, en CORS : l’origine de production, l’alias stable de la branche de preview, et l’URL propre au déploiement. Pas de joker. Le stockage se choisit avec `BLOB_READ_WRITE_TOKEN` seulement (pas d’OIDC).

### Après un déploiement

Une migration ratée rate le déploiement. Deux builds attendent le verrou, puis le second échoue au bout de 180 secondes si le premier le tient encore. Ne pas lancer Alembic vers la production depuis une machine pendant un déploiement.

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

1. les contrôles backend sous Ubuntu et Windows, avec Python 3.12 et SQLite ;
2. les mêmes tests backend sous Ubuntu contre un service Postgres 16 ;
3. l'audit des dépendances runtime Python sous Ubuntu ;
4. les contrôles frontend et l'audit npm sous Ubuntu, avec Node.js 24 ;
5. la validation Compose et le test Docker complet, toujours sur SQLite.

Les actions GitHub sont référencées par SHA de commit. Les paquets applicatifs sont
installés depuis les lockfiles ; les images de base utilisent des tags de version maintenue
(`python:3.12-slim-bookworm`, `node:24-alpine`, `nginxinc/nginx-unprivileged:1.28-alpine`).
Ces tags restent mutables : une reconstruction future peut recevoir des correctifs système.
La reproductibilité octet pour octet des images nécessitera le gel de leurs digests lors
d'une publication, avec une procédure régulière de mise à jour de sécurité.

**Vérification de cette phase :** Docker n'est pas installé dans le poste de travail
ayant produit cette modification. Son exécution distante a été confirmée avec succès dans
la [CI #4](https://github.com/leobrowncode/SoloLMNP/actions/runs/35065201132) :
construction, migrations, HTTP, utilisateurs non root et persistance.

## Sources techniques consultées le 15 septembre 2026

- [Services Compose : santé, dépendances, montages et restrictions](https://docs.docker.com/reference/compose-file/services/)
- [Interpolation et valeurs par défaut de Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Image Nginx sans privilèges et chemins temporaires](https://github.com/nginx/docker-nginx-unprivileged)
- [Installation npm ci à partir du lockfile](https://docs.npmjs.com/cli/v11/commands/npm-ci/)
- [Configuration officielle de Node.js dans GitHub Actions](https://github.com/actions/setup-node)
