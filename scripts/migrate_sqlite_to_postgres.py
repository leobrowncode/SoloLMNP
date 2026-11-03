"""Copy an existing SQLite dossier into Postgres and check the ledger.

The SQLite file must already be at the current schema. The Postgres database
is migrated to that schema first. Balances of validated entries, the FEC and
the liasse (JSON, CSV, PDF) are compared before the copy is kept. Documents
stay in DOCUMENTS_DIR; this script moves the database only.

Use the direct Neon URL (without ``-pooler``). The running application can
keep the pooled URL.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.database import SCHEMA_REVISION  # noqa: E402
from app.services.sqlite_transfer import copy_sqlite_to_postgres  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, help="Chemin du fichier SQLite source")
    parser.add_argument("--database-url", required=True, help="URL Postgres cible, sans -pooler")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Remplace un dossier déjà présent dans Postgres",
    )
    args = parser.parse_args()
    database = Path(args.sqlite).expanduser().resolve()
    if not database.is_file():
        raise SystemExit(f"Fichier SQLite introuvable : {database}")
    source = Settings(
        _env_file=None,
        database_url=f"sqlite:///{database.as_posix()}",
        documents_dir=database.parent / "documents",
    )
    target = Settings(_env_file=None, database_url=args.database_url)
    if target.uses_sqlite:
        raise SystemExit("La cible doit être une URL Postgres.")
    url = make_url(target.database_url)
    if url.host and "-pooler" in url.host:
        raise SystemExit(
            "Utilisez l’URL Neon directe pour la copie et les migrations, pas l’hôte -pooler."
        )
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.attributes["settings"] = target
    command.upgrade(config, "head")
    report = copy_sqlite_to_postgres(source, target, replace=args.replace)
    print(f"Révision : {SCHEMA_REVISION}")
    print(f"Cible : {url.host}/{url.database}")
    print(f"Lignes copiées : {report['rows']}")
    print(
        "Balances validées : identiques "
        f"({report['accounts']} compte(s), {report['fiscal_years']} exercice(s))"
    )
    print(f"FEC : identique ({report['fec_bytes']} octets)")
    print("Liasse JSON, CSV et PDF : identique")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
