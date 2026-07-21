from __future__ import annotations

import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from sagp_core.membership import (
    MemberRecord,
    MembershipCreateRequest,
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

    CREATE_FIELDS = {
        "first_name", "last_name", "primary_email", "institution", "region",
        "notes", PUBLIC_EXPIRATION_FIELD,
    }
    REQUIRED_CREATE_FIELDS = {"first_name", "last_name", PUBLIC_EXPIRATION_FIELD}
    CREATE_FIELD_MAX_LENGTHS = {
        "first_name": 120, "last_name": 120, "primary_email": 254,
        "institution": 300, "region": 120, "notes": 4000,
    }
    REQUIRED_MEMBER_COLUMNS = {
        "person_id", "display_name", "first_name", "last_name", "institution",
        "primary_email", "secondary_email", "region", "membership_status", "last_paid_year",
        "active", "notes", "created_at", "updated_at",
    }
    EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    PERSON_ID_PATTERN = re.compile(r"^SAGP(\d{6})$")

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

    def build_membership_create_request(
        self,
        proposed_member_data: dict[str, Any],
        reason: str,
        requested_by: str,
        source: str = "manual",
        notes: str | None = None,
    ) -> MembershipCreateRequest:
        return MembershipCreateRequest(
            proposed_member_data=proposed_member_data,
            reason=reason,
            requested_by=requested_by,
            source=source,
            notes=notes,
        )

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").strip().casefold().split())

    def _database_compatibility_errors(self, con: sqlite3.Connection | None = None) -> list[str]:
        owns_connection = con is None
        connection = con or self._connect()
        try:
            columns = {row[1] for row in connection.execute("PRAGMA table_info(members)")}
            missing = sorted(self.REQUIRED_MEMBER_COLUMNS - columns)
            return [f"Membership database is missing required columns: {', '.join(missing)}."] if missing else []
        finally:
            if owns_connection:
                connection.close()

    def validate_create_request(self, request: MembershipCreateRequest) -> list[str]:
        errors: list[str] = []
        if request.request_type != "membership_create":
            errors.append("request_type must be 'membership_create'.")
        if not isinstance(request.proposed_member_data, dict):
            return errors + ["proposed_member_data must be an object."]
        if not str(request.request_id).strip():
            errors.append("request_id is required.")
        elif not str(request.request_id).startswith("mcr_"):
            errors.append("request_id must begin with 'mcr_'.")
        if not str(request.requested_at).strip():
            errors.append("requested_at is required.")
        else:
            try:
                datetime.fromisoformat(str(request.requested_at).replace("Z", "+00:00"))
            except ValueError:
                errors.append("requested_at must be an ISO 8601 date and time.")
        if not str(request.requested_by).strip():
            errors.append("requested_by is required.")
        elif len(str(request.requested_by).strip()) > 120:
            errors.append("requested_by may not exceed 120 characters.")
        if not str(request.reason).strip():
            errors.append("reason is required.")
        elif len(str(request.reason).strip()) > 500:
            errors.append("reason may not exceed 500 characters.")

        data = request.proposed_member_data
        unexpected = sorted(set(data) - self.CREATE_FIELDS)
        if unexpected:
            errors.append(f"Unsupported proposed member fields: {', '.join(unexpected)}.")
        for field in sorted(self.REQUIRED_CREATE_FIELDS):
            if not str(data.get(field) or "").strip():
                errors.append(f"{field.replace('_', ' ')} is required.")
        for field, maximum in self.CREATE_FIELD_MAX_LENGTHS.items():
            value = data.get(field)
            if value is not None and not isinstance(value, (str, int)):
                errors.append(f"{field.replace('_', ' ')} must be text.")
            elif len(str(value or "").strip()) > maximum:
                errors.append(f"{field.replace('_', ' ')} may not exceed {maximum} characters.")
        email = str(data.get("primary_email") or "").strip()
        if email and not self.EMAIL_PATTERN.fullmatch(email):
            errors.append("primary email must be a valid email address.")
        value = data.get(self.PUBLIC_EXPIRATION_FIELD)
        try:
            year = int(value)
            if isinstance(value, bool) or year < 1900 or year > 2100:
                errors.append("membership expiration year must be between 1900 and 2100.")
        except (TypeError, ValueError):
            errors.append("membership expiration year must be an integer year.")
        try:
            errors.extend(self._database_compatibility_errors())
        except (FileNotFoundError, sqlite3.Error) as exc:
            errors.append(f"Membership database is not compatible or unavailable: {exc}")
        return errors

    def find_create_duplicates(
        self, request: MembershipCreateRequest, con: sqlite3.Connection | None = None
    ) -> list[dict[str, Any]]:
        data = request.proposed_member_data
        email = self._normalize_text(data.get("primary_email"))
        first = self._normalize_text(data.get("first_name"))
        last = self._normalize_text(data.get("last_name"))
        institution = self._normalize_text(data.get("institution"))
        owns_connection = con is None
        connection = con or self._connect()
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(
                "SELECT person_id, display_name, first_name, last_name, institution, primary_email, secondary_email FROM members"
            ).fetchall()
        finally:
            if owns_connection:
                connection.close()
        matches: list[dict[str, Any]] = []
        for row in rows:
            row_emails = {self._normalize_text(row["primary_email"]), self._normalize_text(row["secondary_email"])} - {""}
            if email and email in row_emails:
                matches.append({"severity": "prohibited", "reason": "exact normalized email match", "person_id": row["person_id"], "display_name": row["display_name"], "institution": row["institution"] or ""})
                continue
            same_name = first and last and first == self._normalize_text(row["first_name"]) and last == self._normalize_text(row["last_name"])
            if same_name:
                same_institution = institution and institution == self._normalize_text(row["institution"])
                matches.append({"severity": "warning", "reason": "exact normalized name and institution" if same_institution else "exact normalized first and last name", "person_id": row["person_id"], "display_name": row["display_name"], "institution": row["institution"] or ""})
        return matches

    def _canonical_create_record(self, request: MembershipCreateRequest) -> dict[str, Any]:
        data = request.proposed_member_data
        first = " ".join(str(data.get("first_name") or "").strip().split())
        last = " ".join(str(data.get("last_name") or "").strip().split())
        expiration = self._as_int(data.get(self.PUBLIC_EXPIRATION_FIELD))
        return {
            "display_name": f"{first} {last}".strip(), "first_name": first,
            "last_name": last, "primary_email": str(data.get("primary_email") or "").strip(),
            "institution": str(data.get("institution") or "").strip(),
            "region": str(data.get("region") or "").strip(),
            "notes": str(data.get("notes") or "").strip(),
            self.DB_EXPIRATION_FIELD: expiration,
            self.PUBLIC_EXPIRATION_FIELD: "" if expiration is None else str(expiration),
            "membership_status": self._derived_status(expiration),
            "derived_membership_status": self._derived_status(expiration), "active": 1,
        }

    def preview_create_request(self, request: MembershipCreateRequest) -> dict[str, Any]:
        errors = self.validate_create_request(request)
        duplicates = [] if errors else self.find_create_duplicates(request)
        return {"request": request.to_dict(), "valid": not errors, "errors": errors,
                "prohibited_duplicate": any(x["severity"] == "prohibited" for x in duplicates),
                "duplicates": duplicates,
                "proposed_record": self._canonical_create_record(request) if isinstance(request.proposed_member_data, dict) else {}}

    def _next_person_id(self, con: sqlite3.Connection) -> str:
        largest = 0
        for (person_id,) in con.execute("SELECT person_id FROM members WHERE person_id LIKE 'SAGP______'"):
            match = self.PERSON_ID_PATTERN.fullmatch(str(person_id))
            if match:
                largest = max(largest, int(match.group(1)))
        if largest >= 999999:
            raise ValueError("No SAGP six-digit person IDs remain available.")
        return f"SAGP{largest + 1:06d}"

    def apply_create_request(self, request: MembershipCreateRequest) -> dict[str, Any]:
        preview = self.preview_create_request(request)
        if not preview["valid"] or preview["prohibited_duplicate"]:
            return {**preview, "applied": False}
        con = self._connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            compatibility_errors = self._database_compatibility_errors(con)
            duplicates = self.find_create_duplicates(request, con)
            if compatibility_errors or any(x["severity"] == "prohibited" for x in duplicates):
                con.rollback()
                return {**preview, "valid": not compatibility_errors, "errors": compatibility_errors,
                        "duplicates": duplicates, "prohibited_duplicate": True, "applied": False}
            record = self._canonical_create_record(request)
            person_id = self._next_person_id(con)
            now = datetime.now().astimezone().isoformat()
            con.execute("""
                INSERT INTO members (
                    person_id, display_name, first_name, last_name, institution,
                    primary_email, region, membership_status, last_paid_year,
                    active, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (person_id, record["display_name"], record["first_name"], record["last_name"],
                  record["institution"], record["primary_email"], record["region"],
                  record["membership_status"], record[self.DB_EXPIRATION_FIELD], 1,
                  record["notes"], now, now))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()
        created = self.get_member(person_id)
        return {**preview, "valid": True, "errors": [], "person_id": person_id,
                "after": created.to_dict() if created else {}, "applied": True}

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
        Apply a validated membership update request to the operational database.

        The canonical membership fact is membership_expiration_year, stored in
        the current SQLite schema as last_paid_year. For compatibility with the
        existing desktop manager and current audience-generation scripts, this
        method also mirrors the derived status into the legacy membership_status
        column when the expiration year changes.
        """

        preview = self.preview_update_request(request)
        if not preview["valid"]:
            return preview

        updates: dict[str, Any] = {}

        for key, value in request.proposed_changes.items():
            db_key = (
                self.DB_EXPIRATION_FIELD
                if key == self.PUBLIC_EXPIRATION_FIELD
                else key
            )
            updates[db_key] = "" if value is None else str(value)

        if self.DB_EXPIRATION_FIELD in updates:
            expiration = self._as_int(updates[self.DB_EXPIRATION_FIELD])
            updates["membership_status"] = self._derived_status(expiration)

        updates["updated_at"] = datetime.now().isoformat()

        if not updates:
            return preview

        assignments = ", ".join(f"{field} = ?" for field in updates)
        values = [updates[field] for field in updates]
        values.append(request.person_id)

        con = self._connect()
        try:
            con.execute(
                f"UPDATE members SET {assignments} WHERE person_id = ?",
                values,
            )
            con.commit()
        finally:
            con.close()

        after_member = self.get_member(request.person_id)

        return {
            "request": request.to_dict(),
            "valid": True,
            "errors": [],
            "before": preview["before"],
            "after": after_member.to_dict() if after_member else {},
            "applied": True,
        }
