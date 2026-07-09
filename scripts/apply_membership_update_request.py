from __future__ import annotations

import argparse
import json
from pathlib import Path

from sagp_core import MembershipUpdateRequest
from sagp_services import MembershipService


def display(value):
    return value if value not in (None, "") else "(blank)"


def main():
    parser = argparse.ArgumentParser(
        description="Apply a MembershipUpdateRequest JSON file."
    )
    parser.add_argument("request_json", help="Path to MembershipUpdateRequest JSON")
    args = parser.parse_args()

    path = Path(args.request_json)
    data = json.loads(path.read_text(encoding="utf-8"))

    request = MembershipUpdateRequest.from_dict(data)
    service = MembershipService()

    preview = service.preview_update_request(request)
    member = service.get_member(request.person_id)

    if member is None:
        print(f"No member found for person_id={request.person_id!r}.")
        raise SystemExit(1)

    if not preview["valid"]:
        print("Update request is invalid:")
        for error in preview["errors"]:
            print(f"- {error}")
        raise SystemExit(1)

    print()
    print("=" * 68)
    print("Membership Update Preview")
    print("=" * 68)
    print(f"Member      : {member.display_name}")
    print(f"Person ID   : {member.person_id}")
    print(f"Request ID  : {request.request_id}")
    print(f"Requested By: {request.requested_by}")
    print(f"Source      : {request.source}")
    print(f"Reason      : {request.reason}")
    print()

    print("Proposed Changes")
    print("-" * 68)

    for field in request.proposed_changes:
        before = preview["before"].get(field, "")
        after = preview["after"].get(field, "")

        print(field.replace("_", " ").title())
        print(f"    Before : {display(before)}")
        print(f"    After  : {display(after)}")
        print()

    before_status = preview["before"].get("derived_membership_status", "")
    after_status = preview["after"].get("derived_membership_status", "")

    if before_status != after_status:
        print("Derived Membership Status")
        print(f"    Before : {display(before_status)}")
        print(f"    After  : {display(after_status)}")
        print()

    print("=" * 68)

    confirm = input("Type YES to apply this update: ")

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
    print("✓ Membership successfully updated")
    print()
    print(f"Member            : {updated['display_name']}")
    print(f"Expiration Year   : {updated.get('membership_expiration_year') or '(blank)'}")
    print(f"Derived Status    : {updated.get('derived_membership_status') or '(blank)'}")
    print()


if __name__ == "__main__":
    main()
