# Relecture de sécurité — 30 octobre 2026

Cette note décrit ce qui a été vérifié pour l’issue #13, ce qui a été corrigé, et ce qui reste accepté. SoloLMNP est mono-utilisateur et auto-hébergé. Les millésimes chargés restent `research_only` : aucun résultat fiscal de cette relecture n’est une base de déclaration.

## Dépendances

- `pip-audit -r backend/requirements.lock --no-deps` : aucune vulnérabilité connue. L’outil signale que le lockfile n’a pas d’empreintes de distribution.
- `npm audit --audit-level=high` dans `frontend/` : aucune vulnérabilité.
- `npm audit` dans `e2e/` (Playwright et axe) : aucune vulnérabilité.

Les lockfiles Python restent sans hash de wheel. Les images `python:3.12-slim-bookworm` et l’image Node du frontend suivent un tag mutable. Ces deux points étaient déjà notés et n’ont pas été changés.

## Confidentialité Git

`.gitignore` exclut `.env`, les bases SQLite, `data/**` (hors `.gitkeep`), `backups/`, `exports/`, les clés, les archives et les rapports Playwright. Les PDF officiels sous `fiscal/**/sources/official/` sont versionnés volontairement. Aucun fichier suivi ne correspond à une base, une sauvegarde, un secret ou un export de dossier.

## Réseau

Le lanceur local lie l’API à `127.0.0.1:8000` et Vite à `127.0.0.1:5173`. CORS est une liste vide par défaut. Les hôtes acceptés sont `localhost`, `127.0.0.1` et `[::1]`. Le proxy Vite retire l’en-tête `Origin`. Les écritures exigent `X-SoloLMNP-Request: 1`.

Compose ne publie que le frontend, sur `127.0.0.1`. Dans le réseau Compose, le conteneur API écoute `0.0.0.0:8000` : le proxy du frontend doit l’atteindre. Ce port n’est pas publié sur l’hôte. Le laisser en `127.0.0.1` dans le conteneur couperait le proxy. Ce n’est pas un correctif à faire.

Il n’y a pas d’authentification. C’est accepté tant que l’écoute reste limitée à la machine locale. Publier l’API, ouvrir le bind, ou élargir CORS expose le dossier sans autre barrière.

## Dépôts et exports

Les justificatifs sont renommés en UUID, contrôlés par signature (PDF, JPEG, PNG) et plafonnés (`max_upload_bytes`, 10 Mio par défaut, 50 Mio au plus). L’import CSV est plafonné à 1 000 000 caractères.

Les CSV d’archive de déclaration et les rejets d’import neutralisent une cellule qui commencerait par `=`, `+`, `@`, une tabulation ou un retour chariot. Un tiret n’est préfixé que s’il n’est pas un montant. Le FEC n’est pas modifié : son format est celui de l’article A47 A-1. L’ouvrir dans un tableur reste un risque résiduel. Le classeur XLSX écrit les cellules en `inlineStr`, pas en formules.

## Restauration

L’archive est refusée si un membre est vide, absolu, dupliqué, contient `..`, une barre oblique inverse, un caractère NUL ou une lettre de lecteur, s’il est un lien (mode Unix), ou si la taille compressée ou le total décompressé dépasse le plafond. Après extraction, le fichier doit rester dans le répertoire temporaire. Une empreinte fausse ou un schéma Alembic différent est refusé. Une sauvegarde est prise avant le remplacement du fichier vivant.

## Correctifs de cette relecture

- Message de dates d’exercice : la fin antérieure au début est nommée, sans le préfixe anglais de Pydantic. L’année de clôture doit être celle de la date de fin. Le millésime n’est pas confondu avec ces dates.
- Neutralisation des formules dans les CSV produits par l’application, hors FEC.
- Contrôles d’archive supplémentaires (barre oblique inverse, NUL, lecteur Windows, lien, volume décompressé, fichier extrait hors du dossier temporaire).
- Le lien d’accueil n’utilise plus un `aria-label` qui masquait le texte visible.
