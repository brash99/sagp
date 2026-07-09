from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WEBSITE = ROOT / "sagp_website"


def run(cmd: list[str], cwd: Path = ROOT, allow_fail: bool = False):
    print()
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode and not allow_fail:
        raise SystemExit(result.returncode)


def output(cmd: list[str], cwd: Path = ROOT) -> str:
    return subprocess.check_output(cmd, cwd=cwd, text=True).strip()


def get_nested(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part, "")
    return "" if cur is None else cur


def set_nested(obj: dict, dotted: str, value):
    cur = obj
    parts = dotted.split(".")
    for part in parts[:-1]:
        cur.setdefault(part, {})
        cur = cur[part]
    cur[parts[-1]] = value


def display(value):
    return value if value not in (None, "") else "(blank)"


def main():
    parser = argparse.ArgumentParser(
        description="Apply a prepared SAGP publication update and deploy refreshed website."
    )
    parser.add_argument("request_json", help="Path to PublicationUpdateRequest JSON")
    parser.add_argument("--no-watch", action="store_true")
    args = parser.parse_args()

    request_path = Path(args.request_json).expanduser().resolve()
    request = json.loads(request_path.read_text(encoding="utf-8"))

    if request.get("request_type") != "publication_update":
        raise SystemExit("Not a publication_update request.")

    publication_type = request.get("publication_type")

    if publication_type not in {"event", "call"}:
        raise SystemExit("This processor currently supports event and call updates.")

    source_yaml = request["context"]["source_yaml"]
    yaml_path = WEBSITE / source_yaml

    if not yaml_path.exists():
        raise SystemExit(f"Source YAML not found: {yaml_path}")

    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    publication = data[publication_type]

    print()
    print("=" * 72)
    print("SAGP Publication Update + Deploy")
    print("=" * 72)
    print(f"Publication : {request.get('publication_title')}")
    print(f"Type        : {request.get('publication_type')}")
    print(f"Request ID  : {request.get('request_id')}")
    print(f"Reason      : {request.get('reason')}")
    print(f"Source YAML : {source_yaml}")
    print()
    print("Changes")
    print("-" * 72)

    for field, change in request["changes"].items():
        expected_before = change.get("before", "")
        current_before = get_nested(publication, field)
        after = change.get("after", "")

        print(field.replace("_", " ").replace(".", " / ").title())
        print(f"    Expected Before : {display(expected_before)}")
        print(f"    Current Before  : {display(current_before)}")
        print(f"    After           : {display(after)}")
        print()

        if str(current_before or "") != str(expected_before or ""):
            raise SystemExit(
                f"Safety check failed for {field!r}: current YAML value does not match request before value."
            )

    print("=" * 72)
    confirm = input("Type YES to apply update, rebuild, commit, push, and deploy: ")

    if confirm != "YES":
        print("Cancelled.")
        return

    for field, change in request["changes"].items():
        set_nested(publication, field, change.get("after", ""))

    yaml_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88),
        encoding="utf-8",
    )

    print()
    print("✓ Canonical YAML updated")

    run(["python3", "-m", "scripts.build_publishing_index"])
    run(["npm", "run", "build"], cwd=WEBSITE)

    run(["git", "add", source_yaml, "public/platform/publishing_index.json"], cwd=WEBSITE)

    website_status = output(["git", "status", "--porcelain"], cwd=WEBSITE)
    if website_status:
        run([
            "git",
            "commit",
            "-m",
            f"Update publication data for {request.get('publication_title')}",
        ], cwd=WEBSITE)
        run(["git", "push"], cwd=WEBSITE)
    else:
        print("No website changes to commit.")

    if not args.no_watch:
        print()
        print("Waiting briefly for GitHub Actions to register the Pages deployment...")
        time.sleep(5)
        run(["gh", "run", "watch"], cwd=WEBSITE, allow_fail=True)

    run(["git", "add", "sagp_website", "scripts/process_publication_update.py"], cwd=ROOT)

    umbrella_status = output(["git", "status", "--porcelain"], cwd=ROOT)
    if umbrella_status:
        run([
            "git",
            "commit",
            "-m",
            "Add publication update processing workflow",
        ], cwd=ROOT)
        run(["git", "push"], cwd=ROOT)

    print()
    print("✓ Publication update processed.")
    print(f"Updated publication : {request.get('publication_title')}")
    print(f"Canonical source    : {source_yaml}")
    print("Check:")
    print("https://sagp-org.github.io/sagp_website/executive/publishing/?v=latest")


if __name__ == "__main__":
    main()
