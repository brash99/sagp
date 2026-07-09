from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass
class AIService:
    model: str | None = None

    def __post_init__(self):
        self.model = self.model or os.getenv("SAGP_AI_MODEL", "gpt-5.5")

    def generate_text(self, prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The openai package is not installed. Run:\n"
                "  python3 -m pip install openai python-dotenv"
            ) from exc

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to /Users/brash/sagp/.env"
            )

        client = OpenAI()

        response = client.responses.create(
            model=self.model,
            input=prompt,
        )

        return response.output_text
