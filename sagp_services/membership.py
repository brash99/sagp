from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sagp_core import MembershipUpdateRequest


@dataclass(frozen=True)
class MemberRecord:
    data: dict[str, Any]

    @property
    def person_id(self) -> str:
        return str(self.data.get("person_id") or "")

    @property
    def display_name(self) -> str:
        return str(self.data.get("display_name") or "")

    @property
    def email(self) -> str:
        return str(
            self.data.get("primary_email")
            or self.data.get("secondary_email")
            or ""
        ).strip()


class MembershipService:
    """
    Service layer for the authoritative operational membership database.

    The Membership Manager owns the live database. This service is the platform
    interface for reading membership state and, later, applying reviewed updates.
    """

    def __init__(self, db_path: str | Path = "sagp_member_manager/output/sagp_members.db"):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Membership database not found: {self.db_path}")

        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _display(value: Any) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _as_int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def list_members(self) -> list[MemberRecord]:
        con = self._connect()
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

        records = []
        for row in rows:
            data = {key: self._display(row[key]) for key in row.keys()}
            data["search_text"] = " ".join([
                data["display_name"],
                data["first_name"],
                data["last_name"],
                data["institution"],
                data["primary_email"],
                data["secondary_email"],
                data["region"],
                data["membership_status"],
                data["last_paid_year"],
            ]).lower()
            records.append(MemberRecord(data))

        return records

    def search_members(self, query: str, limit: int = 50) -> list[MemberRecord]:
        terms = query.strip().lower().split()
        if not terms:
            return []

        matches = [
            member for member in self.list_members()
            if all(term in member.data["search_text"] for term in terms)
        ]

        return matches[:limit]

    def get_member(self, person_id: str) -> MemberRecord | None:
        for member in self.list_members():
            if member.person_id == person_id:
                return member
        return None

    def statistics(self) -> dict[str, Any]:
        members = self.list_members()
        current_year = datetime.now().year

        status_counts = Counter(
            member.data.get("membership_status") or "(blank)"
            for member in members
        )

        last_paid_counts = Counter(
            member.data.get("last_paid_year") or "(blank)"
            for member in members
        )

        members_with_email = [member for member in members if member.email]

        paid_current = [
            member for member in members
            if member.data.get("membership_status") == "Current Member"
        ]

        expired = [
            member for member in members
            if member.data.get("membership_status") == "Past Member"
        ]

        paid_this_year = [
            member for member in members
            if self._as_int(member.data.get("last_paid_year")) == current_year
        ]

        not_renewed_this_year = [
            member for member in members
            if self._as_int(member.data.get("last_paid_year")) is not None
            and self._as_int(member.data.get("last_paid_year")) < current_year
        ]

        return {
            "generated_at": datetime.now().isoformat(),
            "source_database": str(self.db_path),
            "current_year": current_year,
            "summary": {
                "total_members": len(members),
                "members_with_email": len(members_with_email),
                "current_paid_members": len(paid_current),
                "expired_members": len(expired),
                "paid_or_renewed_this_year": len(paid_this_year),
                "not_renewed_this_year": len(not_renewed_this_year),
                "unknown_or_blank_status": (
                    status_counts.get("Unknown A", 0)
                    + status_counts.get("Unknown B", 0)
                    + status_counts.get("(blank)", 0)
                ),
            },
            "membership_status_counts": dict(sorted(status_counts.items())),
            "last_paid_year_counts": dict(
                sorted(last_paid_counts.items(), key=lambda kv: str(kv[0]))
            ),
        }


    ALLOWED_UPDATE_FIELDS = {
        "display_name",
        "first_name",
        "last_name",
        "institution",
        "primary_email",
        "secondary_email",
        "phone",
        "city",
        "state_province",
        "country",
        "region",
        "membership_status",
        "member_since",
        "last_paid_year",
        "active",
        "notes",
    }

    VALID_MEMBERSHIP_STATUSES = {
        "",
        "Current Member",
        "Past Member",
        "Executive and Donors",
        "Unknown A",
        "Unknown B",
    }

    def validate_update_request(
        self,
        request: MembershipUpdateRequest,
    ) -> list[str]:
        errors = []

        if not request.person_id.strip():
            errors.append("person_id is required.")

        if not request.proposed_changes:
            errors.append("proposed_changes may not be empty.")

        member = self.get_member(request.person_id)
        if member is None:
            errors.append(f"No member found for person_id={request.person_id!r}.")

        for field in request.proposed_changes:
            if field not in self.ALLOWED_UPDATE_FIELDS:
                errors.append(f"Field {field!r} may not be updated.")

        if "membership_status" in request.proposed_changes:
            status = str(request.proposed_changes["membership_status"] or "")
            if status not in self.VALID_MEMBERSHIP_STATUSES:
                errors.append(f"Invalid membership_status: {status!r}.")

        if "last_paid_year" in request.proposed_changes:
            value = request.proposed_changes["last_paid_year"]
            if value not in ("", None):
                try:
                    year = int(value)
                    if year < 1900 or year > 2100:
                        errors.append("last_paid_year must be between 1900 and 2100.")
                except (TypeError, ValueError):
                    errors.append("last_paid_year must be blank or an integer year.")

        return errors

    def preview_update_request(
        self,
        request: MembershipUpdateRequest,
    ) -> dict[str, Any]:
        member = self.get_member(request.person_id)
        errors = self.validate_update_request(request)

        before = member.data if member else {}
        after = dict(before)
        if not errors:
            for key, value in request.proposed_changes.items():
                after[key] = "" if value is None else str(value)

        return {
            "request": request.to_dict(),
            "valid": not errors,
            "errors": errors,
            "before": before,
            "after": after,
        }


    def export_records_payload(self) -> dict[str, Any]:        members = self.list_members()

        return {
            "generated_at": datetime.now().isoformat(),
            "source_database": str(self.db_path),
            "member_count": len(members),
            "members": [member.data for member in members],
        }
