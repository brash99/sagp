from __future__ import annotations

import json
from pathlib import Path

from sagp_services import MembershipService


OUTPUT_PATH = Path("sagp_website/public/platform/membership_dashboard.json")


def main():
    service = MembershipService()
    dashboard = service.statistics()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(dashboard, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
