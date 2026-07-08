from __future__ import annotations

import json
from pathlib import Path

from sagp_services import PlatformService


def summary_to_dict(item):
    return {
        "object_type": item.object_type,
        "object_id": item.object_id,
        "title": item.title,
        "detail": item.detail,
        "path": str(item.path),
    }


def main():
    root = Path(".")
    platform = PlatformService(root)

    manifest = {
        "audiences": [summary_to_dict(item) for item in platform.list_audiences()],
        "messages": [summary_to_dict(item) for item in platform.list_messages()],
        "communications": [summary_to_dict(item) for item in platform.list_communications()],
    }

    output_path = root / "output" / "platform_manifest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(output_path)


if __name__ == "__main__":
    main()
