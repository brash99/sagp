from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .communication import Audience, Communication, Message


def write_json_artifact(data: Dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return path


def load_json_artifact(input_path: str | Path) -> Dict[str, Any]:
    path = Path(input_path)

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_audience(audience: Audience, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    filename = f"{audience.audience_id}.json"
    return write_json_artifact(audience.to_dict(), output_dir / filename)


def save_message(message: Message, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    filename = f"{message.message_id}.json"
    return write_json_artifact(message.to_dict(), output_dir / filename)


def save_communication(communication: Communication, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    filename = f"{communication.communication_id}.json"
    return write_json_artifact(communication.to_dict(), output_dir / filename)


def load_audience_dict(input_path: str | Path) -> Dict[str, Any]:
    return load_json_artifact(input_path)


def load_message_dict(input_path: str | Path) -> Dict[str, Any]:
    return load_json_artifact(input_path)


def load_communication_dict(input_path: str | Path) -> Dict[str, Any]:
    return load_json_artifact(input_path)
