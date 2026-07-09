from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml
from docx import Document


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "sagp_website"


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return value or "event"


def read_docx_text(path: Path) -> list[str]:
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return paragraphs


def build_event_yaml(paragraphs: list[str], event_type: str, year: str) -> dict:
    title = paragraphs[0] if paragraphs else f"{year} {event_type.replace('_', ' ').title()}"
    subtitle = paragraphs[1] if len(paragraphs) > 1 else ""
    description = "\n\n".join(paragraphs[2:]) if len(paragraphs) > 2 else ""

    event_id = f"{event_type.replace('_', '-')}-{year}"

    return {
        "event": {
            "id": event_id,
            "title": title,
            "subtitle": subtitle,
            "type": event_type,
            "status": "draft",
            "description": description,
            "attendance": {
                "instructions": "",
                "contact_email": "",
            },
            "dates": {
                "start": "",
                "end": "",
                "timezone": "",
                "timezone_iana": "",
            },
            "location": {
                "mode": "",
                "venue": "",
                "city": "",
                "region": "",
                "country": "",
                "url": "",
            },
            "hero": {
                "kicker": title,
                "title": subtitle or title,
                "subtitle": "",
                "image": "/assets/images/parthenon_night.jpg",
            },
            "sessions": [],
        }
    }


def main():
    parser = argparse.ArgumentParser(
        description="Create a draft SAGP event YAML file from a finalized DOCX source document."
    )
    parser.add_argument("docx", help="Path to source .docx file")
    parser.add_argument("--type", required=True, choices=["annual_conference", "distinguished_lectureship"])
    parser.add_argument("--year", required=True)
    args = parser.parse_args()

    docx_path = Path(args.docx).expanduser().resolve()
    if not docx_path.exists():
        raise SystemExit(f"DOCX not found: {docx_path}")

    paragraphs = read_docx_text(docx_path)
    data = build_event_yaml(paragraphs, args.type, args.year)

    out_dir = WEBSITE / "content/events" / args.type
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / f"{args.year}.draft.yaml"

    out_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )

    print("Created draft event YAML:")
    print(f"  {out_path}")
    print()
    print("Review and edit this draft before publishing.")


if __name__ == "__main__":
    main()
