from __future__ import annotations

from typing import Any

from sagp_core import (
    Audience,
    Communication,
    CommunicationEngineContract,
    Message,
)


class CommunicationEngine(CommunicationEngineContract):
    """
    Version 1 implementation of the Communication capability.

    The engine composes an Audience and a Message into a
    Communication derived object.

    Future versions may add validation, policy enforcement,
    scheduling, auditing, delivery metadata, and governance checks.
    """

    def compose(
        self,
        audience: Audience,
        message: Message,
        **kwargs: Any,
    ) -> Communication:

        if not audience.recipients:
            raise ValueError("Audience contains no recipients.")

        if not message.subject.strip():
            raise ValueError("Message subject may not be empty.")

        if (
            not message.rich_html.strip()
            and not message.plain_text.strip()
        ):
            raise ValueError(
                "Message contains no content."
            )

        return Communication(
            audience=audience,
            message=message,
            created_by=kwargs.get("created_by"),
            delivery_metadata=kwargs.get(
                "delivery_metadata",
                {},
            ),
        )
