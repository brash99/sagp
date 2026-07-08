from __future__ import annotations

import json
import shutil
from pathlib import Path

from sagp_services import PlatformService


def copy_object(item, public_root: Path, folder: str) -> dict:
    target_dir = public_root / "knowledge_objects" / folder
    target_dir.mkdir(parents=True, exist_ok=True)

    target_path = target_dir / item.path.name
    shutil.copy2(item.path, target_path)

    return {
        "object_type": item.object_type,
        "object_id": item.object_id,
        "title": item.title,
        "detail": item.detail,
        "url": f"/platform/knowledge_objects/{folder}/{item.path.name}",
    }


def main():
    root = Path(".")
    public_root = root / "sagp_website" / "public" / "platform"
    public_root.mkdir(parents=True, exist_ok=True)

    platform = PlatformService(root)

    manifest = {
        "audiences": [
            copy_object(item, public_root, "audiences")
            for item in platform.list_audiences()
        ],
        "messages": [
            copy_object(item, public_root, "messages")
            for item in platform.list_messages()
        ],
        "communications": [
            copy_object(item, public_root, "communications")
            for item in platform.list_communications()
        ],
    }

    manifest_path = public_root / "platform_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(manifest_path)


if __name__ == "__main__":
    main()
