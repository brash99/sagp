from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from .communication import Audience, Communication, Message


class MembershipEngineContract(ABC):
    """
    Contract for any engine that transforms canonical membership knowledge
    into an Audience derived object.
    """

    @abstractmethod
    def generate_audience(self, **kwargs: Any) -> Audience:
        raise NotImplementedError


class PublishingEngineContract(ABC):
    """
    Contract for any engine that transforms canonical publishing knowledge
    into a Message derived object.
    """

    @abstractmethod
    def generate_message(self, **kwargs: Any) -> Message:
        raise NotImplementedError


class CommunicationEngineContract(ABC):
    """
    Contract for any engine that composes an Audience and Message into
    a Communication derived object.
    """

    @abstractmethod
    def compose(
        self,
        audience: Audience,
        message: Message,
        **kwargs: Any,
    ) -> Communication:
        raise NotImplementedError


class ArtifactStoreContract(ABC):
    """
    Contract for storing and retrieving SAGP derived objects as durable artifacts.
    """

    @abstractmethod
    def save(self, artifact: Dict[str, Any], **kwargs: Any) -> str:
        raise NotImplementedError

    @abstractmethod
    def load(self, artifact_id: str, **kwargs: Any) -> Dict[str, Any]:
        raise NotImplementedError
