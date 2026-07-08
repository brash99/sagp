from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from sagp_core.membership import (
    MemberRecord,
    MembershipStatistics,
    MembershipUpdateRequest,
)


class MembershipService:
    """
    Service layer for SAGP canonical member records.

    Constitutional scope:
      - owns member lookup, member facts, membership expiration, and statistics
      - does not own communications, audiences, email export, or payment records

    Membership state rule:
      - canonical fact: membership_expiration_year, currently stored in the DB
        as last_paid_year
      - derived meaning: current/past status
      - grace rule: current if expiration_year >= current_year - 1
    """

    DB_EXPIRATION_FIELD = "last_paid_year"
    PUBLIC_EXPIRATION_FIELD = "membership_expiration_year"
    GRACE_YEARS = 1

    DETAIL_UPDATE_FIELDS = {
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
        "notes",
    }

    EXPIRATION_UPDATE_FIELDS = {
        PUBLIC_EXPIRATION_FIELD,
        DB_EXPIRATION_FIELD,
    }

    ALLOWED_UPDATE_FIELDS = DETAIL_UPDATE_FIELDS | EXPIRATION_UPDATE_FIELDS

    def __init__(self, db_path: str | Path = "sagp_member_manager/output/sagp_members.db"):
        self.db_path = Path(db_path)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

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

    def _derived_status(self, expiration_year: int | None, current_year: int | None = None) -> str:
        if expiration_year is None:
            return ""

        year = current_year or datetime.now().year
        if expiration_year >= year - self.GRACE_YEARS:
            return "Current Member"
        return "Past Member"

    def _row_to_member_record(self, row: sqlite3.Row) -> MemberRecord:
        data = {key: self._display(row[key]) for key in row.keys()}

        expiration = self._as_int(data.get(self.DB_EXPIRATION_FIELD))
        data[self.PUBLIC_EXPIRATION_FIELD] = "" if expiration is None else str(expiration)
        data["derived_membership_status"] = self._derived_status(expiration)

        data["search_text"] = " ".join([
            data.get("display_name", ""),
            data.get("first_name", ""),
            data.get("last_name", ""),
            data.get("institution", ""),
            data.get("primary_email", ""),
            data.get("secondary_email", ""),
            data.get("region", ""),
            data.get("membership_status", ""),
            data.get("derived_membership_status", ""),
            data.get(self.DB_EXPIRATION_FIELD, ""),
            data.get(self.PUBLIC_EXPIRATION_FIELD, ""),
        ]).lower()

        return MemberRecord(data)

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

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

        return [self._row_to_member_record(row) for row in rows]

    def search_members(self, query: str, limit: int = 50) -> list[MemberRecord]:
        terms = query.strip().lower().split()
        if not terms:
            return []

        matches = [
            member
            for member in self.list_members()
            if all(term in member.data["search_text"] for term in terms)
        ]

        return matches[:limit]

    def get_member(self, person_id: str) -> MemberRecord | None:
        con = self._connect()
        row = con.execute("""
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
            WHERE person_id = ?
        """, (person_id,)).fetchone()
        con.close()

        if row is None:
            return None
        return self._row_to_member_record(row)

    def statistics(self) -> dict[str, Any]:
        members = self.list_members()
        current_year = datetime.now().year

        stored_status_counts = Counter(
            member.data.get("membership_status") or "(blank)"
            for member in members
        )

        derived_status_counts = Counter(
            member.data.get("derived_membership_status") or "(blank)"
            for member in members
        )

        expiration_counts = Counter(
            member.data.get(self.PUBLIC_EXPIRATION_FIELD) or "(blank)"
            for member in members
        )

        members_with_email = [member for member in members if member.email]

        current_members = [
            member for member in members
            if member.data.get("derived_membership_status") == "Current Member"
        ]

        past_members = [
            member for member in members
            if member.data.get("derived_membership_status") == "Past Member"
        ]

        paid_or_renewed_this_year = [
            member for member in members
            if member.expiration_year == current_year
        ]

        not_renewed_this_year = [
            member for member in members
            if member.expiration_year is not None
            and member.expiration_year < current_year
        ]

        stats = MembershipStatistics(
            generated_at=datetime.now().isoformat(),
            source_database=str(self.db_path),
            current_year=current_year,
            summary={
                "total_members": len(members),
                "members_with_email": len(members_with_email),
                "current_paid_members": len(current_members),
                "expired_members": len(past_members),
                "paid_or_renewed_this_year": len(paid_or_renewed_this_year),
                "not_renewed_this_year": len(not_renewed_this_year),
                "unknown_or_blank_status": (
                    stored_status_counts.get("Unknown A", 0)
                    + stored_status_counts.get("Unknown B", 0)
                    + stored_status_counts.get("(blank)", 0)
                ),
            },
            membership_status_counts=dict(sorted(stored_status_counts.items())),
            expiration_year_counts=dict(
                sorted(expiration_counts.items(), key=lambda kv: str(kv[0]))
            ),
        )

        data = stats.to_dict()
        data["derived_membership_status_counts"] = dict(sorted(derived_status_counts.items()))
        return data

    def export_records_payload(self) -> dict[str, Any]:
        members = self.list_members()

        return {
            "generated_at": datetime.now().isoformat(),
            "source_database": str(self.db_path),
            "member_count": len(members),
            "members": [member.to_dict() for member in members],
        }

    # ------------------------------------------------------------------
    # Domain operations
    # ------------------------------------------------------------------

    def build_member_detail_update_request(
        self,
        person_id: str,
        proposed_changes: dict[str, Any],
        reason: str,
        requested_by: str,
        source: str = "manual",
        notes: str | None = None,
    ) -> MembershipUpdateRequest:
        return MembershipUpdateRequest(
            person_id=person_id,
            proposed_changes=proposed_changes,
            reason=reason,
            requested_by=requested_by,
            source=source,
            notes=notes,
        )

    def build_membership_expiration_update_request(
        self,
        person_id: str,
        expiration_year: int | str,
        reason: str,
        requested_by: str,
        source: str = "manual",
        notes: str | None = None,
    ) -> MembershipUpdateRequest:
        return MembershipUpdateRequest(
            person_id=person_id,
            proposed_changes={
                self.PUBLIC_EXPIRATION_FIELD: expiration_year,
            },
            reason=reason,
            requested_by=requested_by,
            source=source,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Validation / preview
    # ------------------------------------------------------------------

    def validate_update_request(self, request: MembershipUpdateRequest) -> list[str]:
        errors: list[str] = []

        if not request.person_id.strip():
            errors.append("person_id is required.")

        if not request.proposed_changes:
            errors.append("proposed_changes may not be empty.")

        if self.get_member(request.person_id) is None:
            errors.append(f"No member found for person_id={request.person_id!r}.")

        for field in request.proposed_changes:
            if field not in self.ALLOWED_UPDATE_FIELDS:
                errors.append(f"Field {field!r} may not be updated by MembershipService.")

        for field in self.EXPIRATION_UPDATE_FIELDS:
            if field in request.proposed_changes:
                value = request.proposed_changes[field]
                try:
                    year = int(value)
                    if year < 1900 or year > 2100:
                        errors.append("membership expiration year must be between 1900 and 2100.")
                except (TypeError, ValueError):
                    errors.append("membership expiration year must be an integer year.")

        return errors

    def preview_update_request(self, request: MembershipUpdateRequest) -> dict[str, Any]:
        member = self.get_member(request.person_id)
        errors = self.validate_update_request(request)

        before = member.to_dict() if member else {}
        after = dict(before)

        if not errors:
            for key, value in request.proposed_changes.items():
                canonical_key = (
                    self.DB_EXPIRATION_FIELD
                    if key == self.PUBLIC_EXPIRATION_FIELD
                    else key
                )
                after[canonical_key] = "" if value is None else str(value)

            expiration = self._as_int(after.get(self.DB_EXPIRATION_FIELD))
            after[self.PUBLIC_EXPIRATION_FIELD] = "" if expiration is None else str(expiration)
            after["derived_membership_status"] = self._derived_status(expiration)

        return {
            "request": request.to_dict(),
            "valid": not errors,
            "errors": errors,
            "before": before,
            "after": after,
        }

    # ------------------------------------------------------------------
    # Future write operation
    # ------------------------------------------------------------------

    def apply_update_request(self, request: MembershipUpdateRequest) -> dict[str, Any]:
        """
        Intentionally not enabled yet.

        Future implementation should:
          1. validate request
          2. create audit record
          3. update database
          4. return before/after state
        """

        preview = self.preview_update_request(request)
        raise NotImplementedError(
            "MembershipService.apply_update_request() is intentionally disabled "
            "until audit logging and write policy are implemented. "
            f"Preview valid={preview['valid']}."
        )
