# Postgres (Neon)

L’application parle à Postgres quand `DATABASE_URL` est une URL Postgres. Le lanceur local, Docker Compose et le parcours navigateur restent sur le fichier SQLite. Les tests par défaut aussi. La CI ajoute un job Ubuntu avec un service Postgres 16.

La migration `0013_account_owner` ajoute `app_account` et `owner_id`. Les lignes déjà présentes sont rattachées au premier compte, encore sans sujet. La première adresse autorisée qui se connecte le réclame. Le plan comptable et les journaux restent partagés. L’écoute locale reste `127.0.0.1`.

## URL

Deux URL Neon, selon l’usage :

| Usage | Hôte |
| --- | --- |
| Application, fonctions courtes | hôte qui contient `-pooler` |
| Migrations Alembic et copie SQLite | hôte direct, sans `-pooler` |

L’hôte pooler est un PgBouncer en mode transaction. Le moteur n’y garde pas de connexion (`NullPool`) et n’y prépare pas de requêtes. Une URL directe, y compris le Postgres de la CI, garde un petit pool avec contrôle de connexion. Rien de tout cela n’est un état global du processus : chaque `Database` possède son moteur.

Les écritures prennent `pg_advisory_xact_lock` pour la durée de la transaction. C’est l’équivalent de `BEGIN IMMEDIATE` sur SQLite : deux requêtes ne peuvent pas valider deux fois la même clé idempotente. Le verrou est transactionnel, donc compatible avec le pooler.

Sur Vercel, Alembic part de `DATABASE_URL_UNPOOLED` pendant le build, avec un verrou de session. Une preview ne migre pas l’hôte de production. Le détail est dans [DEPLOYMENT.md](DEPLOYMENT.md).

Le pilote est `postgresql+psycopg`. Une URL `postgresql://` est réécrite ainsi. Les options acceptées sont `sslmode`, `channel_binding`, `connect_timeout` et `application_name`.

Le fuseau de session est UTC, pour que `CURRENT_DATE` corresponde à `date('now')` de SQLite.

## Schéma

Les migrations `0001` à `0013_account_owner` sont la source SQLite. Sur Postgres elles sont traduites à l’exécution : `GLOB` et `typeof`, dates, `printf`, booléens `0`/`1`, et les triggers `RAISE(ABORT, …)` qui deviennent des fonctions PL/pgSQL. Les écritures validées restent immuables. Le journal validé reste la seule source des balances, des états, du FEC et de la liasse.

Les centimes tiennent dans un entier 64 bits. SQLite les stocke dans `INTEGER`. Postgres les stocke dans `NUMERIC` sans échelle : un `BIGINT` arrondirait une écriture SQL fractionnaire avant le `CHECK`, alors que `typeof` doit encore la refuser. Les identifiants, années, durées et taux restent des `INTEGER`, avec une séquence (le rowid SQLite n’a pas d’équivalent). Les triggers d’intégrité lèvent l’errcode `23514`, pour que l’API les voie comme un conflit d’intégrité, comme l’`ABORT` SQLite.

Les index partiels (une seule écriture d’à-nouveaux, un seul instantané courant) existent des deux côtés.

## Copier un dossier SQLite

Le fichier source doit être à la révision `0013_account_owner` (ouvrir l’application une fois, ou laisser Alembic le migrer). La cible est migrée par le script. Elle doit être vide de dossier, sauf avec `--replace`.

```sh
python scripts/migrate_sqlite_to_postgres.py \
  --sqlite data/sololmnp.sqlite3 \
  --database-url 'postgresql://USER:PASSWORD@HOST/DB?sslmode=require'
```

Le script désactive les triggers utilisateur le temps de l’insertion, laisse les clés étrangères actives, puis compare avant de garder la copie :

- balances des écritures validées, par compte, en centimes ;
- FEC de chaque exercice, octet par octet ;
- liasse JSON, CSV et PDF, octet par octet.

Les justificatifs ne bougent pas avec ce script : pointez `DOCUMENTS_DIR` vers le même dossier, ou posez `BLOB_READ_WRITE_TOKEN` pour un magasin privé (voir [BACKUP.md](BACKUP.md)). La sauvegarde zip fichier reste réservée à SQLite (`BACKUP_SQLITE_ONLY`). L’archive de dossier (`POST /api/filing/dossier/export`) emporte les lignes et les justificatifs enregistrés, sur Postgres comme sur SQLite.

## Tests

```sh
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/postgres \
  python -m pytest
```

Chaque test reçoit une base vide clonée d’un modèle déjà migré. `python scripts/check.py` continue d’utiliser SQLite.
