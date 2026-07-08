from __future__ import annotations

import json
from pathlib import Path

from sagp_services import MembershipService


OUTPUT_PATH = Path("sagp_website/public/platform/membership_records.json")


def main():
    service = MembershipService()
    payload = service.export_records_payload()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)
    print(f"{payload['member_count']:,} member records exported")


if __name__ == "__main__":
    main()
