from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path


DB_PATH = Path("sagp_member_manager/output/sagp_members.db")
OUTPUT_PATH = Path("sagp_website/public/platform/membership_dashboard.json")


def display(value):
    return "" if value is None else str(value)


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    members = con.execute("SELECT * FROM members").fetchall()
    con.close()

    current_year = datetime.now().year

    status_counts = Counter(display(m["membership_status"]) or "(blank)" for m in members)
    last_paid_counts = Counter(display(m["last_paid_year"]) or "(blank)" for m in members)

    members_with_email = [
        m for m in members
        if display(m["primary_email"] or m["secondary_email"]).strip()
    ]

    paid_current = [
        m for m in members
        if display(m["membership_status"]) == "Current Member"
    ]

    expired = [
        m for m in members
        if display(m["membership_status"]) == "Past Member"
    ]

    expiring_or_recent = [
        m for m in members
        if as_int(m["last_paid_year"]) == current_year
    ]

    not_renewed_this_year = [
        m for m in members
        if as_int(m["last_paid_year"]) is not None
        and as_int(m["last_paid_year"]) < current_year
    ]

    dashboard = {
        "generated_at": datetime.now().isoformat(),
        "source_database": str(DB_PATH),
        "current_year": current_year,
        "summary": {
            "total_members": len(members),
            "members_with_email": len(members_with_email),
            "current_paid_members": len(paid_current),
            "expired_members": len(expired),
            "paid_or_renewed_this_year": len(expiring_or_recent),
            "not_renewed_this_year": len(not_renewed_this_year),
            "unknown_or_blank_status": (
                status_counts.get("Unknown A", 0)
                + status_counts.get("Unknown B", 0)
                + status_counts.get("(blank)", 0)
            ),
        },
        "membership_status_counts": dict(sorted(status_counts.items())),
        "last_paid_year_counts": dict(sorted(last_paid_counts.items(), key=lambda kv: str(kv[0]))),
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(dashboard, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
