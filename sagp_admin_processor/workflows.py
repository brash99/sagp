from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable
from uuid import uuid4

import yaml
from docx import Document

from sagp_core import MembershipCreateRequest, MembershipUpdateRequest
from sagp_services import MembershipService


class JobKind(str, Enum):
    MEMBERSHIP_UPDATE = "Membership update"
    MEMBERSHIP_CREATE = "New member"
    PUBLICATION_UPDATE = "Publication update"
    EVENT_DOCX = "New event document"
    UNSUPPORTED = "Unsupported file"


@dataclass
class PreviewResult:
    kind: JobKind
    valid: bool
    title: str
    summary: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class SnapshotItem:
    original: Path
    backup: Path
    existed: bool
    is_dir: bool


@dataclass
class AppliedChange:
    change_id: str
    kind: JobKind
    title: str
    source_file: Path
    snapshot_dir: Path
    snapshot_items: list[SnapshotItem]
    website_paths: set[str] = field(default_factory=set)
    details: dict = field(default_factory=dict)


def get_nested(obj: dict, dotted: str):
    current = obj
    for part in dotted.split("."):
        if not isinstance(current, dict):
            return ""
        current = current.get(part, "")
    return "" if current is None else current


def set_nested(obj: dict, dotted: str, value) -> None:
    current = obj
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def display(value) -> str:
    return "(blank)" if value in (None, "") else str(value)


class AdminProcessor:
    """Safe local processing layer used by the PySide6 application."""

    def __init__(
        self,
        root: str | Path | None = None,
        state_dir: str | Path | None = None,
        run_artifact_builders: bool = True,
    ):
        self.root = Path(root or Path(__file__).resolve().parents[1]).resolve()
        self.website = self.root / "sagp_website"
        self.db_path = self.root / "sagp_member_manager/output/sagp_members.db"
        self.state_dir = Path(state_dir or Path(__file__).resolve().parent / ".state")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.run_artifact_builders = run_artifact_builders
        self.applied: list[AppliedChange] = []
        self.deployment_phase = "local"

    # ---------- detection and preview ----------

    def preview_file(
        self,
        path: str | Path,
        event_type: str | None = None,
        event_year: str | None = None,
    ) -> PreviewResult:
        source = Path(path).expanduser().resolve()
        if not source.exists():
            return PreviewResult(JobKind.UNSUPPORTED, False, source.name, "", ["File not found."])
        if source.suffix.lower() == ".docx":
            return self._preview_docx(source, event_type, event_year)
        if source.suffix.lower() != ".json":
            return PreviewResult(JobKind.UNSUPPORTED, False, source.name, "", ["Choose a JSON or DOCX file."])
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return PreviewResult(JobKind.UNSUPPORTED, False, source.name, "", [f"Invalid JSON: {exc}"])
        if not isinstance(data, dict):
            return PreviewResult(JobKind.UNSUPPORTED, False, source.name, "", ["JSON must contain one object."])
        if data.get("request_type") == "membership_create":
            return self._preview_membership_create(source, data)
        if data.get("request_type") == "publication_update":
            return self._preview_publication(source, data)
        if "person_id" in data and "proposed_changes" in data:
            return self._preview_membership_update(source, data)
        if data.get("communication_id"):
            return PreviewResult(
                JobKind.UNSUPPORTED,
                False,
                source.name,
                "This is a Communication export, not an administrative request.",
                ["No Edward-side processing workflow exists for Communication JSON."],
            )
        return PreviewResult(JobKind.UNSUPPORTED, False, source.name, "", ["Request type was not recognized."])

    def _preview_membership_update(self, source: Path, data: dict) -> PreviewResult:
        try:
            request = MembershipUpdateRequest.from_dict(data)
            service = MembershipService(self.db_path)
            preview = service.preview_update_request(request)
        except Exception as exc:
            return PreviewResult(JobKind.MEMBERSHIP_UPDATE, False, source.name, "", [str(exc)])
        member = preview.get("before", {})
        lines = [
            f"Member: {member.get('display_name') or request.person_id}",
            f"Person ID: {request.person_id}",
            f"Request ID: {request.request_id}",
            f"Reason: {request.reason}",
            "",
            "Proposed changes:",
        ]
        for key in request.proposed_changes:
            lines.append(f"• {key.replace('_', ' ').title()}: {display(preview['before'].get(key))} → {display(preview['after'].get(key))}")
        return PreviewResult(JobKind.MEMBERSHIP_UPDATE, preview["valid"], member.get("display_name") or request.person_id, "\n".join(lines), preview["errors"], metadata={"request": request})

    def _preview_membership_create(self, source: Path, data: dict) -> PreviewResult:
        try:
            request = MembershipCreateRequest.from_dict(data)
            service = MembershipService(self.db_path)
            preview = service.preview_create_request(request)
        except Exception as exc:
            return PreviewResult(JobKind.MEMBERSHIP_CREATE, False, source.name, "", [str(exc)])
        record = preview.get("proposed_record", {})
        duplicates = preview.get("duplicates", [])
        warnings = [f"{item['reason']}: {item['display_name']} ({item['person_id']})" for item in duplicates]
        errors = list(preview["errors"])
        if preview.get("prohibited_duplicate"):
            errors.append("Creation is blocked by an exact normalized email match.")
        lines = [
            f"New member: {record.get('display_name')}",
            f"Email: {display(record.get('primary_email'))}",
            f"Institution: {display(record.get('institution'))}",
            f"Expiration year: {display(record.get('membership_expiration_year'))}",
            f"Derived status: {display(record.get('derived_membership_status'))}",
            f"Reason: {request.reason}",
        ]
        return PreviewResult(JobKind.MEMBERSHIP_CREATE, preview["valid"] and not preview.get("prohibited_duplicate"), record.get("display_name") or source.name, "\n".join(lines), errors, warnings, {"request": request})

    def _preview_publication(self, source: Path, request: dict) -> PreviewResult:
        errors: list[str] = []
        publication_type = request.get("publication_type")
        if publication_type not in {"event", "call"}:
            errors.append("Publication type must be event or call.")
        source_yaml = request.get("context", {}).get("source_yaml", "")
        yaml_path = (self.website / source_yaml).resolve()
        try:
            yaml_path.relative_to(self.website.resolve())
        except ValueError:
            errors.append("Source YAML must be inside the website repository.")
        if not yaml_path.exists():
            errors.append(f"Source YAML not found: {source_yaml}")
        changes = request.get("changes")
        if not isinstance(changes, dict) or not changes:
            errors.append("Publication request contains no changes.")
        publication = {}
        if not errors:
            try:
                loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                publication = loaded[publication_type]
            except Exception as exc:
                errors.append(f"Could not load canonical publication: {exc}")
        lines = [
            f"Publication: {request.get('publication_title') or request.get('publication_id')}",
            f"Type: {publication_type}",
            f"Request ID: {request.get('request_id')}",
            f"Reason: {request.get('reason')}",
            f"Source: {source_yaml}",
            "",
            "Proposed changes:",
        ]
        if not errors:
            for field_name, change in changes.items():
                if not isinstance(change, dict) or "before" not in change or "after" not in change:
                    errors.append(f"Change {field_name} must contain before and after values.")
                    continue
                before = change.get("before", "") if isinstance(change, dict) else ""
                after = change.get("after", "") if isinstance(change, dict) else ""
                current = get_nested(publication, field_name)
                lines.append(f"• {field_name}: {display(current)} → {display(after)}")
                if str(current or "") != str(before or ""):
                    errors.append(f"Safety check failed for {field_name}: canonical value no longer matches the request.")
        return PreviewResult(JobKind.PUBLICATION_UPDATE, not errors, request.get("publication_title") or source.name, "\n".join(lines), errors, metadata={"request": request, "yaml_path": yaml_path})

    def _preview_docx(self, source: Path, event_type: str | None, event_year: str | None) -> PreviewResult:
        errors: list[str] = []
        if event_type not in {"annual_conference", "distinguished_lectureship"}:
            errors.append("Choose Annual Conference or Distinguished Lectureship.")
        if not str(event_year or "").isdigit() or not 2000 <= int(event_year or 0) <= 2100:
            errors.append("Enter an event year between 2000 and 2100.")
        try:
            paragraphs = [p.text.strip() for p in Document(source).paragraphs if p.text.strip()]
        except Exception as exc:
            errors.append(f"Could not read Word document: {exc}")
            paragraphs = []
        if not paragraphs:
            errors.append("The Word document contains no readable paragraphs.")
        type_label = (event_type or "event").replace("_", " ").title()
        lines = [f"Document: {source.name}", f"Event type: {type_label}", f"Year: {event_year or '(not set)'}", "", "Document preview:"]
        lines.extend(f"• {text}" for text in paragraphs[:20])
        if len(paragraphs) > 20:
            lines.append(f"… and {len(paragraphs) - 20} more paragraphs")
        return PreviewResult(JobKind.EVENT_DOCX, not errors, f"{type_label} {event_year or ''}".strip(), "\n".join(lines), errors, metadata={"event_type": event_type, "event_year": str(event_year or "")})

    # ---------- local apply and rollback ----------

    def process(self, source: str | Path, preview: PreviewResult, log: Callable[[str], None] | None = None) -> AppliedChange:
        if not preview.valid:
            raise ValueError("The file must pass validation before processing.")
        source_path = Path(source).resolve()
        logger = log or (lambda _: None)
        if preview.kind == JobKind.MEMBERSHIP_UPDATE:
            return self._apply_membership(source_path, preview, False, logger)
        if preview.kind == JobKind.MEMBERSHIP_CREATE:
            return self._apply_membership(source_path, preview, True, logger)
        if preview.kind == JobKind.PUBLICATION_UPDATE:
            return self._apply_publication(source_path, preview, logger)
        if preview.kind == JobKind.EVENT_DOCX:
            return self._apply_event_docx(source_path, preview, logger)
        raise ValueError("Unsupported workflow.")

    def _make_snapshot(self, paths: list[Path], kind: JobKind, title: str, source: Path) -> AppliedChange:
        change_id = f"change_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        snapshot_dir = self.state_dir / change_id
        snapshot_dir.mkdir(parents=True)
        items: list[SnapshotItem] = []
        for index, original in enumerate(paths):
            original = original.resolve()
            backup = snapshot_dir / f"item_{index}"
            existed = original.exists()
            is_dir = original.is_dir() if existed else False
            if existed:
                if is_dir:
                    shutil.copytree(original, backup)
                elif original == self.db_path.resolve():
                    with sqlite3.connect(original) as source_db, sqlite3.connect(backup) as backup_db:
                        source_db.backup(backup_db)
                else:
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(original, backup)
            items.append(SnapshotItem(original, backup, existed, is_dir))
        change = AppliedChange(change_id, kind, title, source, snapshot_dir, items)
        (snapshot_dir / "manifest.json").write_text(json.dumps({"change_id": change_id, "kind": kind.value, "title": title, "source": str(source), "created_at": datetime.now().isoformat()}, indent=2), encoding="utf-8")
        return change

    def _membership_snapshot_paths(self) -> list[Path]:
        return [
            self.db_path,
            self.website / "public/platform/membership_dashboard.json",
            self.website / "public/platform/membership_records.json",
            self.root / "output/audiences",
            self.website / "public/platform/knowledge_objects/audiences",
            self.website / "public/platform/platform_manifest.json",
        ]

    def _apply_membership(self, source: Path, preview: PreviewResult, creating: bool, log: Callable[[str], None]) -> AppliedChange:
        change = self._make_snapshot(self._membership_snapshot_paths(), preview.kind, preview.title, source)
        service = MembershipService(self.db_path)
        try:
            request = preview.metadata["request"]
            result = service.apply_create_request(request) if creating else service.apply_update_request(request)
            if not result.get("valid") or (creating and not result.get("applied")):
                raise ValueError("; ".join(result.get("errors", [])) or "Membership operation was not applied.")
            log(f"Membership database updated: {result.get('person_id') or request.person_id}")
            if self.run_artifact_builders:
                self._run([sys.executable, "-m", "scripts.build_membership_dashboard_data"], self.root, log)
                self._run([sys.executable, "-m", "scripts.build_membership_records"], self.root, log)
                if creating:
                    self._run([sys.executable, "-m", "scripts.generate_standard_audiences"], self.root, log)
                    self._run([sys.executable, "-m", "scripts.publish_platform_manifest_to_website"], self.root, log)
            change.website_paths.update({"public/platform/membership_dashboard.json", "public/platform/membership_records.json"})
            if creating:
                change.website_paths.update({"public/platform/platform_manifest.json", "public/platform/knowledge_objects/audiences"})
            change.details = result
            self.applied.append(change)
            return change
        except Exception:
            self._restore(change)
            raise

    def _apply_publication(self, source: Path, preview: PreviewResult, log: Callable[[str], None]) -> AppliedChange:
        request = preview.metadata["request"]
        yaml_path: Path = preview.metadata["yaml_path"]
        index_path = self.website / "public/platform/publishing_index.json"
        change = self._make_snapshot([yaml_path, index_path], preview.kind, preview.title, source)
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            publication = data[request["publication_type"]]
            for field_name, field_change in request["changes"].items():
                current = get_nested(publication, field_name)
                if str(current or "") != str(field_change.get("before", "") or ""):
                    raise ValueError(f"Safety check failed for {field_name}.")
                set_nested(publication, field_name, field_change.get("after", ""))
            yaml_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88), encoding="utf-8")
            if self.run_artifact_builders:
                self._run([sys.executable, "-m", "scripts.build_publishing_index"], self.root, log)
            relative_yaml = str(yaml_path.relative_to(self.website))
            change.website_paths.update({relative_yaml, "public/platform/publishing_index.json"})
            change.details = {"request": request, "source_yaml": relative_yaml}
            log(f"Canonical publication updated: {relative_yaml}")
            self.applied.append(change)
            return change
        except Exception:
            self._restore(change)
            raise

    def _apply_event_docx(self, source: Path, preview: PreviewResult, log: Callable[[str], None]) -> AppliedChange:
        event_type = preview.metadata["event_type"]
        year = preview.metadata["event_year"]
        draft_path = self.website / "content/events" / event_type / f"{year}.draft.yaml"
        canonical_path = self.website / "content/events" / event_type / f"{year}.yaml"
        if canonical_path.exists():
            raise FileExistsError(f"A canonical event already exists for {event_type} {year}.")
        change = self._make_snapshot([draft_path, canonical_path], preview.kind, preview.title, source)
        try:
            self._run([sys.executable, "-m", "scripts.create_event_from_docx_ai", str(source), "--type", event_type, "--year", year], self.root, log)
            if not draft_path.exists():
                raise RuntimeError("Event assistant did not create the expected draft file.")
            change.website_paths.add(str(draft_path.relative_to(self.website)))
            change.details = {"draft_path": str(draft_path), "canonical_path": str(canonical_path), "event_type": event_type, "year": year}
            self.applied.append(change)
            log(f"Draft ready for review: {draft_path}")
            return change
        except Exception:
            self._restore(change)
            raise

    def back_out_last(self) -> AppliedChange:
        if self.deployment_phase != "local":
            raise ValueError("Rollback is unavailable because the deployment commit has already begun. Resume deployment instead.")
        if not self.applied:
            raise ValueError("There are no uncommitted changes to back out.")
        change = self.applied.pop()
        self._restore(change)
        return change

    def back_out_all(self) -> list[AppliedChange]:
        reverted: list[AppliedChange] = []
        while self.applied:
            reverted.append(self.back_out_last())
        return reverted

    def _restore(self, change: AppliedChange) -> None:
        for item in reversed(change.snapshot_items):
            if item.original.exists():
                if item.original.is_dir():
                    shutil.rmtree(item.original)
                else:
                    item.original.unlink()
            if item.existed:
                item.original.parent.mkdir(parents=True, exist_ok=True)
                if item.is_dir:
                    shutil.copytree(item.backup, item.original)
                else:
                    shutil.copy2(item.backup, item.original)
        shutil.rmtree(change.snapshot_dir, ignore_errors=True)

    # ---------- deploy ----------

    def deployment_summary(self) -> str:
        if not self.applied:
            return "No locally processed changes are awaiting deployment."
        lines = ["The following local changes will be committed and deployed:", ""]
        for change in self.applied:
            lines.append(f"• {change.kind.value}: {change.title}")
            if change.kind == JobKind.EVENT_DOCX:
                lines.append("  The reviewed draft will be promoted to the public event collection.")
        lines.extend(["", "The website will be built, committed, pushed, and its GitHub Pages deployment watched.", "The umbrella repository submodule pointer will then be committed and pushed."])
        return "\n".join(lines)

    def deploy(self, log: Callable[[str], None] | None = None, watch: bool = True) -> None:
        if not self.applied:
            raise ValueError("No processed changes are awaiting deployment.")
        logger = log or (lambda _: None)
        if self.deployment_phase == "local":
            if self._output(["git", "diff", "--cached", "--name-only"], self.website):
                raise RuntimeError("The website repository already has staged changes. Unstage or commit them before deploying through the app.")
            if self._output(["git", "diff", "--cached", "--name-only"], self.root):
                raise RuntimeError("The umbrella repository already has staged changes. Unstage or commit them before deploying through the app.")
            website_paths: set[str] = set()
            promoted = False
            for change in self.applied:
                website_paths.update(change.website_paths)
                if change.kind == JobKind.EVENT_DOCX:
                    draft = Path(change.details["draft_path"])
                    canonical = Path(change.details["canonical_path"])
                    data = yaml.safe_load(draft.read_text(encoding="utf-8"))
                    data["event"]["status"] = "upcoming"
                    canonical.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=88), encoding="utf-8")
                    draft.unlink()
                    promoted = True
                    website_paths.discard(str(draft.relative_to(self.website)))
                    website_paths.add(str(canonical.relative_to(self.website)))
            if promoted and self.run_artifact_builders:
                self._run([sys.executable, "-m", "scripts.build_publishing_index"], self.root, logger)
                website_paths.add("public/platform/publishing_index.json")
            self._run(["npm", "run", "build"], self.website, logger)
            self._run(["git", "add", "--", *sorted(website_paths)], self.website, logger)
            staged = self._output(["git", "diff", "--cached", "--name-only"], self.website)
            if not staged:
                raise RuntimeError("No website changes were staged; deployment stopped.")
            title = self.applied[0].title if len(self.applied) == 1 else f"{len(self.applied)} administrative changes"
            self._run(["git", "commit", "-m", f"Process {title}"], self.website, logger)
            self.deployment_phase = "website_committed"
        if self.deployment_phase == "website_committed":
            self._run(["git", "push"], self.website, logger)
            self.deployment_phase = "website_pushed"
            if watch:
                import time
                logger("Waiting five seconds for GitHub Actions…")
                time.sleep(5)
                self._run(["gh", "run", "watch"], self.website, logger, allow_fail=True)
        if self.deployment_phase == "website_pushed":
            self._run(["git", "add", "sagp_website"], self.root, logger)
            if self._output(["git", "diff", "--cached", "--name-only"], self.root):
                self._run(["git", "commit", "-m", "Update website after administrative processing"], self.root, logger)
            self.deployment_phase = "umbrella_committed"
        if self.deployment_phase == "umbrella_committed":
            self._run(["git", "push"], self.root, logger)
            self.deployment_phase = "complete"
        for change in self.applied:
            shutil.rmtree(change.snapshot_dir, ignore_errors=True)
        self.applied.clear()
        self.deployment_phase = "local"

    def _run(self, cmd: list[str], cwd: Path, log: Callable[[str], None], allow_fail: bool = False) -> None:
        log(f"$ {' '.join(cmd)}")
        process = subprocess.Popen(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert process.stdout is not None
        for line in process.stdout:
            log(line.rstrip())
        code = process.wait()
        if code and not allow_fail:
            raise subprocess.CalledProcessError(code, cmd)

    @staticmethod
    def _output(cmd: list[str], cwd: Path) -> str:
        return subprocess.check_output(cmd, cwd=cwd, text=True).strip()
