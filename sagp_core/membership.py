from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MemberRecord:
    """Canonical read model for one member record."""

    data: Dict[str, Any]

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

    @property
    def expiration_year(self) -> int | None:
        value = self.data.get("membership_expiration_year") or self.data.get("last_paid_year")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)


@dataclass(frozen=True)
class MembershipStatistics:
    generated_at: str
    source_database: str
    current_year: int
    summary: Dict[str, Any]
    membership_status_counts: Dict[str, int]
    expiration_year_counts: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Backward compatibility for the current dashboard.
        data["last_paid_year_counts"] = data["expiration_year_counts"]
        return data


@dataclass(frozen=True)
class MembershipUpdateRequest:
    """
    Reviewable request to change a member record.

    This object stores proposed factual changes. The MembershipService validates
    and interprets their meaning.
    """

    person_id: str
    proposed_changes: Dict[str, Any]
    reason: str
    requested_by: str
    request_id: str = field(default_factory=lambda: f"mur_{uuid4().hex[:12]}")
    requested_at: str = field(default_factory=now_iso)
    source: str = "manual"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MembershipUpdateRequest":
        return cls(**data)


@dataclass(frozen=True)
class MembershipCreateRequest:
    """Reviewable request to create one canonical member record."""

    proposed_member_data: Dict[str, Any]
    reason: str
    requested_by: str
    request_type: str = "membership_create"
    request_id: str = field(default_factory=lambda: f"mcr_{uuid4().hex[:12]}")
    requested_at: str = field(default_factory=now_iso)
    source: str = "manual"
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MembershipCreateRequest":
        return cls(**data)
