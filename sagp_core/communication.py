from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeliveryStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    EXPORTED = "exported"
    SENT = "sent"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class Recipient:
    person_id: str
    name: str
    email: str
    membership_status: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    eligibility_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Recipient":
        return cls(**data)


@dataclass(frozen=True)
class Audience:
    name: str
    description: str
    criteria: Dict[str, Any]
    recipients: List[Recipient]
    audience_id: str = field(default_factory=lambda: f"aud_{uuid4().hex[:12]}")
    generated_at: str = field(default_factory=now_iso)
    source_engine: str = "membership"

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "recipients": [r.to_dict() for r in self.recipients],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Audience":
        payload = dict(data)
        payload["recipients"] = [
            Recipient.from_dict(r)
            for r in payload.get("recipients", [])
        ]
        return cls(**payload)


@dataclass(frozen=True)
class Message:
    title: str
    subject: str
    rich_html: str
    plain_text: str
    source_yaml: Optional[str] = None
    message_type: Optional[str] = None
    attachments_or_links: List[str] = field(default_factory=list)
    message_id: str = field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    generated_at: str = field(default_factory=now_iso)
    source_engine: str = "publishing"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(**data)


@dataclass(frozen=True)
class Communication:
    audience: Audience
    message: Message
    created_by: Optional[str] = None
    delivery_metadata: Dict[str, Any] = field(default_factory=dict)
    audit_notes: List[str] = field(default_factory=list)
    communication_id: str = field(default_factory=lambda: f"com_{uuid4().hex[:12]}")
    created_at: str = field(default_factory=now_iso)
    delivery_status: DeliveryStatus = DeliveryStatus.DRAFT

    @property
    def recipients(self) -> List[Recipient]:
        return self.audience.recipients

    @property
    def subject(self) -> str:
        return self.message.subject

    @property
    def rich_html(self) -> str:
        return self.message.rich_html

    @property
    def plain_text(self) -> str:
        return self.message.plain_text

    def summary(self) -> Dict[str, Any]:
        return {
            "communication_id": self.communication_id,
            "audience_id": self.audience.audience_id,
            "audience_name": self.audience.name,
            "message_id": self.message.message_id,
            "message_title": self.message.title,
            "subject": self.subject,
            "recipient_count": len(self.recipients),
            "delivery_status": self.delivery_status.value,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "communication_id": self.communication_id,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "delivery_status": self.delivery_status.value,
            "delivery_metadata": self.delivery_metadata,
            "audit_notes": self.audit_notes,
            "audience": self.audience.to_dict(),
            "message": self.message.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Communication":
        payload = dict(data)
        payload["audience"] = Audience.from_dict(payload["audience"])
        payload["message"] = Message.from_dict(payload["message"])
        payload["delivery_status"] = DeliveryStatus(payload["delivery_status"])
        return cls(**payload)
