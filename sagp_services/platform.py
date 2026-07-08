from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from sagp_core import (
    Audience,
    Communication,
    Message,
    load_audience_dict,
    load_communication_dict,
    load_message_dict,
    save_communication,
)
from sagp_engines.communication import CommunicationEngine


KnowledgeObjectType = Literal["audience", "message", "communication"]


@dataclass(frozen=True)
class KnowledgeObjectSummary:
    object_type: KnowledgeObjectType
    object_id: str
    title: str
    path: Path
    detail: str = ""


class PlatformService:
    """
    Service layer for discovering, loading, composing, and saving SAGP
    knowledge objects.

    This is intentionally thin. It knows where artifacts live and which engine
    to call, but it does not contain business logic.
    """

    def __init__(self, root: str | Path = "."):
        self.root = Path(root)
        self.output_dir = self.root / "output"
        self.audience_dir = self.output_dir / "audiences"
        self.message_dir = self.output_dir / "messages"
        self.communication_dir = self.output_dir / "communications"
        self.communication_engine = CommunicationEngine()

    def list_audiences(self) -> list[KnowledgeObjectSummary]:
        summaries = []

        for path in sorted(self.audience_dir.glob("*.json")):
            try:
                audience = Audience.from_dict(load_audience_dict(path))
            except Exception:
                continue

            summaries.append(
                KnowledgeObjectSummary(
                    object_type="audience",
                    object_id=audience.audience_id,
                    title=audience.name,
                    path=path,
                    detail=f"{len(audience.recipients):,} recipients",
                )
            )

        return summaries

    def list_messages(self) -> list[KnowledgeObjectSummary]:
        summaries = []

        for path in sorted(self.message_dir.glob("*.json")):
            try:
                message = Message.from_dict(load_message_dict(path))
            except Exception:
                continue

            summaries.append(
                KnowledgeObjectSummary(
                    object_type="message",
                    object_id=message.message_id,
                    title=message.title,
                    path=path,
                    detail=message.subject,
                )
            )

        return summaries

    def list_communications(self) -> list[KnowledgeObjectSummary]:
        summaries = []

        for path in sorted(self.communication_dir.glob("*.json")):
            try:
                communication = Communication.from_dict(load_communication_dict(path))
            except Exception:
                continue

            summaries.append(
                KnowledgeObjectSummary(
                    object_type="communication",
                    object_id=communication.communication_id,
                    title=communication.subject,
                    path=path,
                    detail=f"{len(communication.recipients):,} recipients; {communication.delivery_status.value}",
                )
            )

        return summaries

    def load_audience(self, path: str | Path) -> Audience:
        return Audience.from_dict(load_audience_dict(path))

    def load_message(self, path: str | Path) -> Message:
        return Message.from_dict(load_message_dict(path))

    def load_communication(self, path: str | Path) -> Communication:
        return Communication.from_dict(load_communication_dict(path))

    def compose_communication(
        self,
        audience: Audience,
        message: Message,
        created_by: str = "platform_service",
    ) -> Communication:
        return self.communication_engine.compose(
            audience,
            message,
            created_by=created_by,
        )

    def save_communication(self, communication: Communication) -> Path:
        return save_communication(communication, self.communication_dir)
