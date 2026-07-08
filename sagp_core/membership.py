from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MembershipUpdateRequest:
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
