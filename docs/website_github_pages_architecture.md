# SAGP Website: GitHub and GitHub Pages Architecture

## Purpose

This document explains the architectural philosophy behind creating, building,
reviewing, and deploying the Society for Ancient Greek Philosophy website with
Git, GitHub, Astro, GitHub Actions, and GitHub Pages.

It complements the broader [SAGP Architecture Manifesto](architecture.md). The
manifesto describes the Society's canonical knowledge, ontology, capabilities,
engines, workspaces, and workflows. This document describes how those ideas are
realized in the website publishing lifecycle.

The central principle is:

> The website is a reproducible publication of reviewed institutional knowledge,
> not the authoritative source of every SAGP fact.

GitHub provides version control, collaboration, automation, and an audit trail.
GitHub Pages delivers the generated public site. Neither should be confused
with the Society's complete knowledge system.

## The repositories and their responsibilities

SAGP currently uses two repositories in the website publication path.

### Umbrella repository: `sagp`

The umbrella repository coordinates the larger SAGP platform. It contains:

- domain objects in `sagp_core`;
- reusable services and engines;
- operational scripts;
- platform-level documentation;
- the SAGP Administrative Processor;
- references to related repositories through Git submodules; and
- the `sagp_website` submodule pointer.

The umbrella repository records which exact revision of the website belongs to
a particular revision of the larger platform. Its submodule pointer is a
versioned relationship, not a second copy of the website.

### Website repository: `sagp_website`

The website repository contains the deployable Astro project. It owns:

- public pages;
- page layouts and visual components;
- website styles and assets;
- structured publication YAML;
- derived JSON artifacts consumed by browser workspaces; and
- the GitHub Actions workflow that deploys the site.

The website is independently versioned because it is independently built and
deployed. A website commit must therefore be created in the website repository
before the umbrella repository can record its new submodule revision.

## Canonical facts and rendered publications

The architecture distinguishes among three kinds of material.

### Canonical knowledge

Canonical knowledge is the authoritative statement of a SAGP fact. Examples
include:

- the operational membership SQLite database;
- canonical event and call YAML;
- governance documents; and
- approved institutional records.

Canonical knowledge should be edited only through a workflow that understands
its schema and validation rules. A rendered webpage is not a substitute for
the canonical fact from which it was produced.

Not all canonical knowledge belongs in a public Git repository. In particular,
the authoritative membership database contains operational information and is
maintained outside the public website repository. Only purpose-built derived
artifacts are published to the website.

### Derived artifacts

Derived artifacts are reproducible outputs created from canonical knowledge.
Examples include membership dashboard JSON, publishing indexes, audiences, and
other browser-readable platform data.

Whenever an existing builder can regenerate an artifact, the builder should be
used instead of editing the artifact manually. This preserves consistency and
makes the provenance of published information understandable.

### Rendered website

Astro transforms source pages, components, structured content, and public
assets into static HTML, CSS, JavaScript, and related files. These generated
files form the deployable website.

The rendered site is disposable in an architectural sense: it should always be
possible to delete the build output and reproduce it from the versioned source.
Generated build output is therefore not the primary object of human editing.

## The publication pipeline

The complete flow is:

```text
Canonical facts or approved request
                  |
                  v
       Validation and local processing
                  |
                  v
     Canonical website content and/or
        regenerated derived artifacts
                  |
                  v
          Local review and build
                  |
                  v
       Commit in sagp_website repository
                  |
                  v
          Push website main branch
                  |
                  v
       GitHub Actions production build
                  |
                  v
         GitHub Pages deployment
                  |
                  v
    Update sagp umbrella submodule pointer
                  |
                  v
       Commit and push umbrella repository
```

Each boundary has a distinct purpose. Combining them carelessly would weaken
review, rollback, and accountability.

## Creating and changing website content

### Human-readable requests

Executive workspaces allow an officer to prepare a request without granting a
web browser authority to mutate canonical state. For example, a Secretary may
download a membership or publication request as JSON, or send an approved Word
document for a new event.

These files are proposals. Downloading one does not alter the membership
database, website repository, or public site.

### Administrative processing

The local Administrative Processor performs the privileged portion of the
workflow. It can:

- load and validate incoming files;
- display proposed changes;
- apply approved changes locally;
- regenerate required artifacts;
- create a reviewable event draft;
- display a website-faithful event preview;
- back out an uncommitted operation; and
- begin publication only after separate approval.

This separation follows a safety principle:

> Preparation, application, review, and publication are different acts and
> should remain visibly different to the administrator.

### Structured content before page-specific markup

Where a fact naturally belongs to a knowledge object, it should be represented
as structured YAML, JSON, a domain object, or a canonical database record. An
Astro component should then render that structure.

This avoids embedding institutional knowledge directly into page layout and
allows the same facts to support webpages, email messages, archives, schedules,
and future applications.

Direct `.astro` editing remains appropriate for page composition, navigation,
explanation, and presentation behavior. It is less appropriate for facts that
already have an established canonical schema.

## Local development and review

The website uses Astro and currently requires the Node version specified by
`sagp_website/package.json`. From the website repository, the principal local
commands are:

```bash
npm install
npm run dev
npm run build
npm run preview
```

- `npm run dev` runs Astro's development server for iterative work.
- `npm run build` creates the production static site in `dist/`.
- `npm run preview` serves that production build locally.

A local build is a validation step, not a deployment. It catches missing
imports, invalid routes, malformed content, and other integration failures
before a commit reaches GitHub.

The Administrative Processor's rich event preview follows the same philosophy:
it builds and renders the local draft using the website itself. The preview is
therefore materially closer to the eventual public page than a plain-text or
YAML summary, while remaining unpublished.

## Git as history and review

Git records intentional changes to versioned source. Every production change
should have a commit whose scope and message make sense to a future maintainer.

A useful commit answers three questions:

1. What changed?
2. Why did it change?
3. Which repository owns that change?

Before committing, the administrator or automation should verify:

- the expected files changed;
- unrelated local work is not included;
- no secrets or private source data are staged;
- generated artifacts correspond to the canonical change;
- relevant tests pass; and
- the Astro production build succeeds.

Git makes a published state identifiable and recoverable. It does not by itself
validate the truth of a change. Human review and domain validation remain
necessary.

## Why the website and umbrella commits are separate

Because `sagp_website` is a Git submodule, there are two related commits:

1. The website commit records the actual content or software change.
2. The umbrella commit records that the platform now points to that website
   revision.

The safe order is:

1. Commit and push `sagp_website`.
2. Confirm the website deployment.
3. Stage the changed `sagp_website` submodule pointer in `sagp`.
4. Commit and push `sagp`.

Updating the umbrella pointer first could refer collaborators to a website
commit that has not been pushed. Forgetting the umbrella update would leave the
two repositories individually valid but out of synchronization.

## GitHub Actions as the production builder

The deployment workflow is stored at:

```text
sagp_website/.github/workflows/deploy.yml
```

It runs when a commit is pushed to the website repository's `main` branch. It
may also be started manually through `workflow_dispatch`.

The workflow has two jobs:

1. **Build** checks out the committed repository and uses the Astro GitHub
   Action with Node 22 to install dependencies, build the static site, and
   upload the Pages artifact.
2. **Deploy** publishes that artifact to the `github-pages` environment using
   GitHub's Pages deployment action.

This clean GitHub-hosted build is important. A successful local build shows
that the administrator's working copy is coherent; a successful Actions build
shows that the committed repository is independently reproducible in the
declared production environment.

The workflow uses deliberately limited permissions:

- `contents: read` to read the website source;
- `pages: write` to publish the Pages artifact; and
- `id-token: write` for GitHub Pages deployment authentication.

No long-lived deployment password is embedded in the website source.

## GitHub Pages and the base path

The Astro configuration declares:

```javascript
site: "https://sagp-org.github.io"
base: "/sagp_website"
```

GitHub Pages hosts this project site below the `/sagp_website` path rather than
at the domain root. Links, assets, browser fetches, and generated routes must
therefore preserve the configured base path.

Hard-coding root-relative URLs such as `/platform/example.json` may work on a
different host while failing on GitHub Pages. Website code should use the
project's established base-path and `platformUrl` conventions so that local
development and Pages deployment resolve the same resources correctly.

## What a deployment means

A deployment is successful only when all of the following are true:

- the intended website commit exists locally;
- that commit has been pushed to GitHub;
- GitHub Actions has built the pushed commit successfully;
- GitHub Pages has accepted and published the artifact;
- the public URL serves the expected revision; and
- the umbrella repository records the deployed website revision.

The words **commit**, **push**, and **deploy** are not interchangeable:

- A **commit** records a local version.
- A **push** transfers commits to GitHub.
- A **deployment** publishes a built artifact through GitHub Pages.

This distinction is especially important during failure recovery. A failed
push, failed Actions build, or failed Pages deployment should be resumed from
the stage that failed rather than creating duplicate commits or repeating an
already applied canonical operation.

## Security and privacy boundaries

The public website repository must never receive credentials or private source
records merely because GitHub is convenient.

In particular:

- OpenAI API keys belong in environment variables or secure credential stores,
  not source files.
- GitHub credentials belong in GitHub CLI, an operating-system credential
  manager, or another approved authentication mechanism.
- The operational membership database should not be committed to the public
  website repository.
- Derived membership artifacts must expose only fields intentionally approved
  for their website or executive-workspace purpose.
- Incoming administrative files should be treated as potentially sensitive and
  should not be staged automatically.

GitHub authorization should follow least privilege. A person who publishes
routine changes needs permission to push approved content and observe the
deployment; that person does not necessarily need permission to delete
repositories, change organization ownership, or modify security settings.

## Failure and recovery philosophy

The system is designed to fail visibly and preserve an understandable state.

### Before commit

Local changes may be reviewed and backed out. The Administrative Processor
creates snapshots for supported operations and restores them in reverse order.

### After commit but before push

The commit is still local. The cause of the failure should be corrected or the
existing commit deliberately revised before retrying the push.

### After website push

The pushed website commit is part of the permanent history even if deployment
fails. The correct response is normally to inspect the Actions failure, make a
new corrective commit if necessary, and deploy again. Rewriting shared history
is discouraged.

### After successful deployment

An erroneous public change should normally be corrected through a new reviewed
change or an explicit revert commit. This preserves an audit trail of what was
published and how it was corrected.

### Umbrella pointer failure

If the website is already pushed and deployed but the umbrella commit fails,
the website should not be republished merely to retry the pointer update. The
existing website revision should be recorded and the umbrella workflow resumed.

## Architectural invariants

Future implementations may replace Astro, GitHub Pages, the desktop toolkit,
or other present technologies. The following invariants should remain:

1. Each institutional fact has an identified canonical owner.
2. Derived artifacts can be regenerated from canonical knowledge.
3. Browser workspaces prepare requests but do not directly mutate canonical
   state.
4. Privileged changes are validated and reviewed before publication.
5. The public site can be reproduced from versioned source.
6. Every deployed revision is identifiable in Git history.
7. Secrets and private operational data remain outside public artifacts.
8. Deployment automation has only the permissions it requires.
9. Failures can be resumed or corrected without silently duplicating changes.
10. The architecture serves SAGP's institutional knowledge rather than making
    that knowledge dependent on a particular user interface or vendor.

## Summary

The SAGP website is built as a static, reproducible publication layer over a
structured institutional knowledge system. Git records reviewed source changes;
GitHub coordinates and preserves those changes; GitHub Actions performs a clean
production build; and GitHub Pages publishes the resulting static artifact.

The value of this design is not merely convenient hosting. It provides a clear
chain from canonical fact, through validated transformation and human approval,
to a specific, reproducible public revision. That chain is what makes the site
maintainable, auditable, recoverable, and transferable to future SAGP officers.
