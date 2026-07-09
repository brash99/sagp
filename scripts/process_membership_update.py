from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from sagp_core import MembershipUpdateRequest
from sagp_services import MembershipService


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "sagp_website"


def run(cmd: list[str], cwd: Path = ROOT):
    print()
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def output(cmd: list[str], cwd: Path = ROOT) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def main():
    parser = argparse.ArgumentParser(
        description="Apply a prepared SAGP membership update and deploy refreshed website data."
    )
    parser.add_argument("request_json", help="Path to MembershipUpdateRequest JSON")
    parser.add_argument(
        "--no-watch",
        action="store_true",
        help="Do not watch the GitHub Pages deployment.",
    )
    args = parser.parse_args()

    request_path = Path(args.request_json).expanduser().resolve()

    if not request_path.exists():
        raise SystemExit(f"Request file not found: {request_path}")

    data = json.loads(request_path.read_text(encoding="utf-8"))
    request = MembershipUpdateRequest.from_dict(data)

    service = MembershipService()
    preview = service.preview_update_request(request)
    member = service.get_member(request.person_id)

    if member is None:
        raise SystemExit(f"No member found for person_id={request.person_id!r}")

    if not preview["valid"]:
        print("Update request is invalid:")
        for error in preview["errors"]:
            print(f"- {error}")
        raise SystemExit(1)

    print()
    print("=" * 72)
    print("SAGP Membership Update + Deploy")
    print("=" * 72)
    print(f"Member     : {member.display_name}")
    print(f"Person ID  : {member.person_id}")
    print(f"Request ID : {request.request_id}")
    print(f"Reason     : {request.reason}")
    print()
    print("Changes")
    print("-" * 72)

    for field in request.proposed_changes:
        before = preview["before"].get(field) or "(blank)"
        after = preview["after"].get(field) or "(blank)"
        print(f"{field.replace('_', ' ').title()}")
        print(f"    Before : {before}")
        print(f"    After  : {after}")
        print()

    before_status = preview["before"].get("derived_membership_status") or "(blank)"
    after_status = preview["after"].get("derived_membership_status") or "(blank)"
    if before_status != after_status:
        print("Derived Membership Status")
        print(f"    Before : {before_status}")
        print(f"    After  : {after_status}")
        print()

    print("=" * 72)
    confirm = input("Type YES to apply update, regenerate data, commit, push, and deploy: ")

    if confirm != "YES":
        print("Cancelled.")
        return

    result = service.apply_update_request(request)

    if not result["valid"]:
        print("Update failed validation:")
        for error in result["errors"]:
            print(f"- {error}")
        raise SystemExit(1)

    updated = result["after"]
    print()
    print("✓ Membership database updated")
    print(f"Member          : {updated.get('display_name')}")
    print(f"Expiration Year : {updated.get('membership_expiration_year') or '(blank)'}")
    print(f"Derived Status  : {updated.get('derived_membership_status') or '(blank)'}")

    run(["python3", "-m", "scripts.build_membership_dashboard_data"])
    run(["python3", "-m", "scripts.build_membership_records"])

    run(["git", "add", "public/platform/membership_dashboard.json", "public/platform/membership_records.json"], cwd=WEBSITE)

    website_status = output(["git", "status", "--porcelain"], cwd=WEBSITE)
    if website_status:
        run([
            "git",
            "commit",
            "-m",
            f"Update membership data for {updated.get('display_name')}",
        ], cwd=WEBSITE)
        run(["git", "push"], cwd=WEBSITE)
    else:
        print()
        print("No website data changes to commit.")

    if not args.no_watch:
        try:
            run(["gh", "run", "watch"], cwd=WEBSITE)
        except subprocess.CalledProcessError:
            print()
            print("No active GitHub Pages run to watch, or watch exited non-zero.")
            print("Continuing with umbrella repository update.")

    run(["git", "add", "sagp_website"], cwd=ROOT)

    umbrella_status = output(["git", "status", "--porcelain"], cwd=ROOT)
    if umbrella_status:
        run([
            "git",
            "commit",
            "-m",
            f"Update website submodule for membership data refresh",
        ], cwd=ROOT)
        run(["git", "push"], cwd=ROOT)
    else:
        print()
        print("No umbrella submodule update to commit.")

    print()
    print("✓ Membership update processed and deployment workflow completed.")
    print()
    print("Check:")
    print("https://sagp-org.github.io/sagp_website/executive/membership/?v=latest")


if __name__ == "__main__":
    main()
