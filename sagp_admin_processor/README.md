# SAGP Administrative Processor

A local PySide6 desktop application for processing files sent by the SAGP
Secretary. It keeps local processing, rollback, and deployment as separate
approval steps.

## Supported inbound files

- Membership update request JSON
- New-member request JSON
- Event or call publication-update JSON
- Finalized event DOCX for an Annual Conference or Distinguished Lectureship

Communication exports and new-call creation are not accepted because the
repository does not currently provide Edward-side processors for them.

## Run

From the umbrella repository:

```bash
cd /Users/brash/sagp
python3 -m sagp_admin_processor
```

On macOS, `launch.command` in this folder can also be opened directly from
Finder.

The application can select several files at once or scan `~/Downloads` for
recognizable requests. DOCX files require an event type and year.

## Safety model

1. Loading a file performs read-only validation and preview.
2. **Process Locally** changes canonical local state and regenerates relevant
   artifacts, but does not commit, push, or deploy.
3. Before each local change, the app snapshots every file or database area that
   operation can modify.
4. **Back Out Last Change** and **Back Out All** restore snapshots in reverse
   order.
5. **Commit, Push & Deploy** is a separate final approval. It builds the site,
   commits only managed paths, pushes the website, watches GitHub Pages, then
   updates and pushes the umbrella submodule pointer.

Rollback is intentionally an uncommitted-session capability. Once a deployment
commit has begun, the app preserves its deployment phase so a failed push can
be retried without creating a second commit. Correcting an already committed
change should be handled as a new reviewed operation.

## Event drafts

Processing an event DOCX runs the existing AI-assisted event generator and
creates a `.draft.yaml` file. Use **Preview Event as Website** to inspect the
actual rich website rendering inside the app. Final deployment promotes the
reviewed draft to canonical event YAML
with `status: upcoming`.

The AI workflow requires the existing `OPENAI_API_KEY` and `SAGP_AI_MODEL`
configuration used by `scripts.create_event_from_docx_ai`.
