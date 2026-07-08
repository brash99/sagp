from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("sagp_member_manager/output/sagp_members.db")
BACKUP_DIR = Path("backups/membership_db")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    db_backup = BACKUP_DIR / f"sagp_members_{stamp}.db"
    sql_dump = BACKUP_DIR / f"sagp_members_{stamp}.sql"
    hash_file = BACKUP_DIR / f"sagp_members_{stamp}.sha256"

    source = sqlite3.connect(DB_PATH)
    target = sqlite3.connect(db_backup)
    source.backup(target)
    target.close()

    with sql_dump.open("w", encoding="utf-8") as f:
        for line in source.iterdump():
            f.write(f"{line}\n")

    source.close()

    hash_file.write_text(
        "\n".join([
            f"{sha256(DB_PATH)}  {DB_PATH}",
            f"{sha256(db_backup)}  {db_backup}",
            f"{sha256(sql_dump)}  {sql_dump}",
            "",
        ]),
        encoding="utf-8",
    )

    print("Created membership snapshot:")
    print(f"  {db_backup}")
    print(f"  {sql_dump}")
    print(f"  {hash_file}")


if __name__ == "__main__":
    main()
