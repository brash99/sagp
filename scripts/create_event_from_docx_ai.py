from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml
from docx import Document

from sagp_services import AIService


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "sagp_website"
PROMPT_PATH = ROOT / "prompts/event_yaml_from_docx.md"


def read_docx_text(path: Path) -> str:
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:yaml|yml)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def normalize_presenter(value):
    if isinstance(value, dict):
        nested = value.get("name")
        if isinstance(nested, dict):
            return {
                "name": str(nested.get("name", "")),
                "institution": str(
                    nested.get("institution")
                    or nested.get("affiliation")
                    or value.get("institution")
                    or value.get("affiliation")
                    or ""
                ),
            }

        return {
            "name": str(value.get("name", "")),
            "institution": str(value.get("institution") or value.get("affiliation") or ""),
        }

    return {"name": str(value), "institution": ""}


def normalize_ai_event_schema(data: dict) -> dict:
    """Normalize common AI output variants into the existing SAGP event schema."""

    def blank_nulls(value):
        if value is None:
            return ""
        if isinstance(value, dict):
            return {k: blank_nulls(v) for k, v in value.items()}
        if isinstance(value, list):
            return [blank_nulls(v) for v in value]
        return value

    data = blank_nulls(data)
    event = data["event"]

    event["id"] = f"{event.get('type', '').replace('_', '-')}-{str(event.get('dates', {}).get('start', ''))[:4] or ''}".strip("-") or event.get("id", "")

    for session in event.get("sessions", []):
        session.setdefault("id", str(session.get("title", "session")).lower().replace(" ", "-"))
        session.setdefault("timezone", event.get("dates", {}).get("timezone", ""))
        session.setdefault("timezone_iana", event.get("dates", {}).get("timezone_iana", ""))

        if session.get("start_time") is not None:
            session["start_time"] = str(session["start_time"]).zfill(5)
        else:
            session["start_time"] = ""

        if session.get("end_time") is None:
            session["end_time"] = ""

        moderator = session.get("moderator")
        if isinstance(moderator, dict) and "affiliation" in moderator:
            moderator["institution"] = moderator.pop("affiliation")

        for index, presentation in enumerate(session.get("presentations", []), start=1):
            if "presenters" not in presentation:
                name = presentation.pop("speaker", "")
                institution = presentation.pop("affiliation", "")
                presentation["presenters"] = [{"name": name, "institution": institution}]

            presentation["presenters"] = [
                normalize_presenter(presenter)
                for presenter in presentation.get("presenters", [])
            ]

            presentation.setdefault(
                "id",
                str(presentation.get("title", f"presentation-{index}"))
                .lower()
                .replace(" ", "-")
                .replace(":", "")
                .replace("?", "")
                .replace("’", "")
                .replace("'", "")
            )
            presentation.setdefault("type", "paper")

    return data

def validate_event_yaml(data: dict, event_type: str, year: str) -> None:
    if not isinstance(data, dict) or "event" not in data:
        raise ValueError("YAML must contain top-level 'event' key.")

    event = data["event"]

    required = [
        "id",
        "title",
        "type",
        "status",
        "description",
        "attendance",
        "dates",
        "location",
        "hero",
        "sessions",
    ]

    for key in required:
        if key not in event:
            raise ValueError(f"event.{key} is missing.")

    if event.get("type") != event_type:
        raise ValueError(f"event.type must be {event_type!r}.")

    if event.get("status") != "draft":
        raise ValueError("event.status must be 'draft'.")

    if not str(event.get("id", "")).endswith(str(year)):
        raise ValueError("event.id should end with the supplied year.")


def main():
    parser = argparse.ArgumentParser(
        description="Create draft SAGP event YAML from DOCX using AI assistance."
    )
    parser.add_argument("docx", help="Path to finalized source .docx file")
    parser.add_argument(
        "--type",
        required=True,
        choices=["annual_conference", "distinguished_lectureship"],
    )
    parser.add_argument("--year", required=True)
    parser.add_argument("--model", default=None)
    parser.add_argument("--dry-run-prompt", action="store_true")
    args = parser.parse_args()

    docx_path = Path(args.docx).expanduser().resolve()
    if not docx_path.exists():
        raise SystemExit(f"DOCX not found: {docx_path}")

    source_text = read_docx_text(docx_path)
    instructions = PROMPT_PATH.read_text(encoding="utf-8")

    prompt = f"""{instructions}

EVENT TYPE:
{args.type}

YEAR:
{args.year}

SOURCE DOCUMENT TEXT:
{source_text}
"""

    if args.dry_run_prompt:
        print(prompt)
        return

    ai = AIService(model=args.model)
    yaml_text = strip_code_fences(ai.generate_text(prompt))

    data = yaml.safe_load(yaml_text)
    data = normalize_ai_event_schema(data)
    validate_event_yaml(data, args.type, args.year)

    out_dir = WEBSITE / "content/events" / args.type
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{args.year}.draft.yaml"
    out_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )

    print("Created AI-assisted draft event YAML:")
    print(f"  {out_path}")
    print()
    print("Review this draft before promoting it to canonical YAML.")


if __name__ == "__main__":
    main()
