from __future__ import annotations

from sagp_core import MembershipUpdateRequest
from sagp_services import MembershipService


def main() -> None:
    service = MembershipService()
    members = service.list_members()
    if not members:
        raise RuntimeError("No members found in membership database.")

    member = members[0]
    request = MembershipUpdateRequest(
        person_id=member.person_id,
        proposed_changes={
            "membership_status": member.data.get("membership_status", ""),
            "last_paid_year": member.data.get("last_paid_year", ""),
            "notes": member.data.get("notes", ""),
        },
        reason="Engineering smoke test; preview only.",
        requested_by="engineering",
        source="smoke_test",
    )

    preview = service.preview_update_request(request)

    print("member:", member.display_name)
    print("person_id:", member.person_id)
    print("valid:", preview["valid"])
    print("errors:", preview["errors"])
    print("warnings:", preview["warnings"])
    print("before keys:", len(preview["before"]))
    print("after keys:", len(preview["after"]))

    try:
        service.apply_update_request(request)
    except NotImplementedError as exc:
        print("apply stub:", exc)
    else:
        raise RuntimeError("apply_update_request unexpectedly performed an update.")


if __name__ == "__main__":
    main()
