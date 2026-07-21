from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from sagp_core import MembershipCreateRequest
from sagp_services import MembershipService


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "sagp_website"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print()
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def output(cmd: list[str], cwd: Path = ROOT) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def load_request(path: Path) -> MembershipCreateRequest:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Could not read request JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Request JSON must contain one object.")
    try:
        return MembershipCreateRequest.from_dict(data)
    except TypeError as exc:
        raise SystemExit(f"Request structure is invalid: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create an SAGP member from an approved request and deploy refreshed website data."
    )
    parser.add_argument("request_json", help="Path to MembershipCreateRequest JSON")
    parser.add_argument("--no-watch", action="store_true", help="Do not watch the GitHub Pages deployment.")
    args = parser.parse_args()
    request_path = Path(args.request_json).expanduser().resolve()
    if not request_path.exists():
        raise SystemExit(f"Request file not found: {request_path}")

    request = load_request(request_path)
    service = MembershipService()
    preview = service.preview_create_request(request)
    if not preview["valid"]:
        print("New-member request is invalid:")
        for error in preview["errors"]:
            print(f"- {error}")
        raise SystemExit(1)

    record = preview["proposed_record"]
    print("\n" + "=" * 72)
    print("SAGP New Member + Deploy")
    print("=" * 72)
    print(f"Request ID    : {request.request_id}")
    print(f"Requested by  : {request.requested_by}")
    print(f"Requested at  : {request.requested_at}")
    print(f"Reason        : {request.reason}")
    print("\nProposed canonical record")
    print("-" * 72)
    for field in ("display_name", "primary_email", "institution", "region", "notes", "last_paid_year"):
        print(f"{field.replace('_', ' ').title():18}: {record.get(field) or '(blank)'}")
    print(f"{'Derived status':18}: {record['derived_membership_status']}")

    print("\nDuplicate check")
    print("-" * 72)
    if not preview["duplicates"]:
        print("No likely duplicates found.")
    else:
        for duplicate in preview["duplicates"]:
            label = "BLOCK" if duplicate["severity"] == "prohibited" else "WARNING"
            institution = f" — {duplicate['institution']}" if duplicate["institution"] else ""
            print(f"{label}: {duplicate['reason']}: {duplicate['display_name']} ({duplicate['person_id']}){institution}")
    if preview["prohibited_duplicate"]:
        raise SystemExit("Insertion blocked because an existing member has the same normalized email address.")

    print("\n" + "=" * 72)
    confirm = input("Type YES to create this member, regenerate data, commit, push, and deploy: ")
    if confirm != "YES":
        print("Cancelled.")
        return

    result = service.apply_create_request(request)
    if not result.get("applied"):
        print("Creation was not applied:")
        for error in result.get("errors", []):
            print(f"- {error}")
        for duplicate in result.get("duplicates", []):
            print(f"- {duplicate['reason']}: {duplicate['display_name']} ({duplicate['person_id']})")
        raise SystemExit(1)

    created = result["after"]
    print(f"\n✓ Membership database updated: {created['display_name']} ({result['person_id']})")
    run(["python3", "-m", "scripts.build_membership_dashboard_data"])
    run(["python3", "-m", "scripts.build_membership_records"])
    run(["python3", "-m", "scripts.generate_standard_audiences"])
    run(["python3", "-m", "scripts.publish_platform_manifest_to_website"])
    run(["npm", "run", "build"], cwd=WEBSITE)
    run([
        "git", "add", "public/platform/membership_dashboard.json",
        "public/platform/membership_records.json", "public/platform/platform_manifest.json",
        "public/platform/knowledge_objects/audiences",
    ], cwd=WEBSITE)

    if output(["git", "status", "--porcelain"], cwd=WEBSITE):
        run(["git", "commit", "-m", f"Add membership data for {created['display_name']}"], cwd=WEBSITE)
        run(["git", "push"], cwd=WEBSITE)
    else:
        print("\nNo website data changes to commit.")

    if not args.no_watch:
        print("\nWaiting briefly for GitHub Actions to register the Pages deployment...")
        time.sleep(5)
        try:
            run(["gh", "run", "watch"], cwd=WEBSITE)
        except subprocess.CalledProcessError:
            print("No active GitHub Pages run to watch, or watch exited non-zero. Continuing.")

    run(["git", "add", "sagp_website"], cwd=ROOT)
    if output(["git", "status", "--porcelain"], cwd=ROOT):
        run(["git", "commit", "-m", "Update website submodule for new membership data"], cwd=ROOT)
        run(["git", "push"], cwd=ROOT)
    else:
        print("\nNo umbrella submodule update to commit.")
    print("\n✓ New-member request processed and deployment workflow completed.")


if __name__ == "__main__":
    main()
