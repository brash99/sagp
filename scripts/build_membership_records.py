from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("sagp_member_manager/output/sagp_members.db")
OUTPUT_PATH = Path("sagp_website/public/platform/membership_records.json")


def display(value):
    return "" if value is None else str(value)


def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT
            person_id,
            display_name,
            first_name,
            last_name,
            institution,
            primary_email,
            secondary_email,
            phone,
            city,
            state_province,
            country,
            region,
            membership_status,
            original_membership_code,
            member_since,
            last_paid_year,
            active,
            notes,
            updated_at
        FROM members
        ORDER BY display_name
    """).fetchall()
    con.close()

    members = []
    for row in rows:
        member = {key: display(row[key]) for key in row.keys()}
        member["search_text"] = " ".join([
            member["display_name"],
            member["first_name"],
            member["last_name"],
            member["institution"],
            member["primary_email"],
            member["secondary_email"],
            member["region"],
            member["membership_status"],
            member["last_paid_year"],
        ]).lower()
        members.append(member)

    payload = {
        "generated_at": datetime.now().isoformat(),
        "source_database": str(DB_PATH),
        "member_count": len(members),
        "members": members,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)
    print(f"{len(members):,} member records exported")


if __name__ == "__main__":
    main()
