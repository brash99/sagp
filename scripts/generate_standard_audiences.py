from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from sagp_core import Audience, Recipient, save_audience


DB_PATH = Path("sagp_member_manager/output/sagp_members.db")
OUTPUT_DIR = Path("output/audiences")


def display(value):
    return "" if value is None else str(value)


def last_paid_year(member):
    try:
        return int(member["last_paid_year"])
    except (TypeError, ValueError):
        return None


def member_email(member):
    return display(member["primary_email"] or member["secondary_email"]).strip()


def make_recipient(member, preset):
    return Recipient(
        person_id=display(member["person_id"]),
        name=display(member["display_name"]),
        email=member_email(member),
        membership_status=display(member["membership_status"]),
        tags=[f"preset:{preset}"],
        eligibility_notes=(
            f"last_paid_year={display(member['last_paid_year'])}; "
            f"region={display(member['region'])}; "
            f"institution={display(member['institution'])}"
        ),
    )


def load_members():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM members").fetchall()
    con.close()
    return rows


def save_preset(name, description, criteria, members):
    recipients = [
        make_recipient(member, name)
        for member in members
        if member_email(member)
    ]

    existing = None
    preset = criteria.get("preset")
    for path in sorted(OUTPUT_DIR.glob("aud_*.json")):
        try:
            candidate = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if candidate.get("criteria", {}).get("preset") == preset:
            existing = candidate
            break

    audience_args = {}
    if existing and existing.get("audience_id"):
        audience_args["audience_id"] = existing["audience_id"]

    audience = Audience(
        name=name,
        description=description,
        criteria=criteria,
        recipients=recipients,
        **audience_args,
    )

    path = save_audience(audience, OUTPUT_DIR)
    print(f"{name}: {len(recipients):,} recipients -> {path}")


def main():
    members = load_members()
    current_year = datetime.now().year

    presets = [
        (
            "All members",
            "All members with email addresses.",
            {"preset": "all_members"},
            members,
        ),
        (
            "Current paid members",
            "Members currently marked as Current Member.",
            {"preset": "current_paid_members"},
            [m for m in members if display(m["membership_status"]) == "Current Member"],
        ),
        (
            "Executive and Board Members",
            "Members marked as Executive and Donors.",
            {"preset": "executive_and_board_members"},
            [m for m in members if display(m["membership_status"]) == "Executive and Donors"],
        ),
        (
            "Expired members",
            "Members currently marked as Past Member.",
            {"preset": "expired_members"},
            [m for m in members if display(m["membership_status"]) == "Past Member"],
        ),
        (
            f"Last paid in {current_year - 1}",
            f"Members whose last paid year is {current_year - 1}.",
            {"preset": "last_paid_in_year", "year": current_year - 1},
            [m for m in members if last_paid_year(m) == current_year - 1],
        ),
        (
            f"Expired before {current_year}",
            f"Members whose last paid year is before {current_year}.",
            {"preset": "expired_before_year", "year": current_year},
            [
                m for m in members
                if last_paid_year(m) is not None
                and last_paid_year(m) < current_year
            ],
        ),
    ]

    for name, description, criteria, selected in presets:
        save_preset(name, description, criteria, selected)


if __name__ == "__main__":
    main()
