from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sagp_core import MembershipCreateRequest
from sagp_services import MembershipService


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sagp_member_import" / "schema" / "sagp_members_schema.sql"


class MembershipCreateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "members.db"
        with sqlite3.connect(self.db_path) as con:
            con.executescript(SCHEMA.read_text(encoding="utf-8"))
        self.service = MembershipService(self.db_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def request(self, **changes) -> MembershipCreateRequest:
        data = {
            "first_name": "Ada",
            "last_name": "Lovelace",
            "primary_email": "ada@example.org",
            "institution": "Analytical Society",
            "region": "",
            "notes": "New membership",
            "membership_expiration_year": str(datetime.now().year),
        }
        data.update(changes)
        return MembershipCreateRequest(
            proposed_member_data=data,
            reason="Membership payment received",
            requested_by="secretary",
        )

    def insert_existing(self, person_id="SAGP000041", first="Ada", last="Lovelace", email="existing@example.org", institution="Analytical Society") -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as con:
            con.execute(
                "INSERT INTO members (person_id, display_name, first_name, last_name, primary_email, institution, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (person_id, f"{first} {last}", first, last, email, institution, now, now),
            )

    def count_members(self) -> int:
        with sqlite3.connect(self.db_path) as con:
            return con.execute("SELECT COUNT(*) FROM members").fetchone()[0]

    def test_valid_request_parsing_and_browser_shape(self) -> None:
        original = self.request()
        parsed = MembershipCreateRequest.from_dict(json.loads(json.dumps(original.to_dict())))
        self.assertEqual(parsed, original)
        self.assertEqual(parsed.request_type, "membership_create")
        self.assertIn("proposed_member_data", parsed.to_dict())
        self.assertTrue(self.service.preview_create_request(parsed)["valid"])

    def test_website_request_generation_shape(self) -> None:
        page = (ROOT / "sagp_website" / "src" / "pages" / "executive" / "membership" / "index.astro").read_text(encoding="utf-8")
        for key in ("proposed_member_data", "reason", "requested_by", "request_type", "request_id", "requested_at"):
            self.assertIn(key, page)
        self.assertIn("membership_create_${safeLastName}_${request.request_id}.json", page)

    def test_missing_required_data(self) -> None:
        errors = self.service.validate_create_request(self.request(first_name=""))
        self.assertIn("first name is required.", errors)

    def test_invalid_email(self) -> None:
        errors = self.service.validate_create_request(self.request(primary_email="not-an-email"))
        self.assertIn("primary email must be a valid email address.", errors)

    def test_invalid_expiration_year(self) -> None:
        errors = self.service.validate_create_request(self.request(membership_expiration_year="twenty"))
        self.assertIn("membership expiration year must be an integer year.", errors)

    def test_derived_status(self) -> None:
        current = self.service.preview_create_request(self.request())["proposed_record"]
        past = self.service.preview_create_request(self.request(membership_expiration_year="1900"))["proposed_record"]
        self.assertEqual(current["derived_membership_status"], "Current Member")
        self.assertEqual(past["derived_membership_status"], "Past Member")

    def test_exact_email_duplicate_is_prohibited(self) -> None:
        self.insert_existing(email=" Ada@Example.ORG ")
        preview = self.service.preview_create_request(self.request())
        self.assertTrue(preview["prohibited_duplicate"])
        self.assertEqual(preview["duplicates"][0]["reason"], "exact normalized email match")

    def test_likely_name_duplicate_warns(self) -> None:
        self.insert_existing(email="different@example.org")
        preview = self.service.preview_create_request(self.request(primary_email="new@example.org"))
        self.assertFalse(preview["prohibited_duplicate"])
        self.assertEqual(preview["duplicates"][0]["severity"], "warning")

    def test_successful_insert_assigns_next_person_id(self) -> None:
        self.insert_existing(person_id="SAGP000041", first="Grace", last="Hopper")
        result = self.service.apply_create_request(self.request())
        self.assertTrue(result["applied"])
        self.assertEqual(result["person_id"], "SAGP000042")
        self.assertEqual(result["after"]["last_paid_year"], str(datetime.now().year))
        self.assertEqual(self.count_members(), 2)

    def test_prohibited_duplicate_does_not_insert(self) -> None:
        self.insert_existing(email="ada@example.org")
        before = self.count_members()
        result = self.service.apply_create_request(self.request())
        self.assertFalse(result["applied"])
        self.assertEqual(self.count_members(), before)

    def test_database_error_rolls_back_insert(self) -> None:
        with sqlite3.connect(self.db_path) as con:
            con.execute("CREATE TRIGGER reject_ada BEFORE INSERT ON members WHEN NEW.first_name = 'Ada' BEGIN SELECT RAISE(ABORT, 'test failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.service.apply_create_request(self.request())
        self.assertEqual(self.count_members(), 0)


if __name__ == "__main__":
    unittest.main()
