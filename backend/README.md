# StageFlow Backend

## Purpose

This directory contains the StageFlow backend workspace created by ED-0002.

The backend is a Python 3.13 FastAPI application managed with `uv`. It is organized around StageFlow's domain boundaries rather than around framework concerns. FastAPI is the HTTP interface layer; it is not the organizing model for the backend.

## Health Endpoint

ED-0002 exposes:

```text
GET /api/v1/health
```

The versioned API path was chosen so future externally visible endpoints can share a consistent routing boundary. The endpoint currently verifies only that the backend process is alive.

## Local Setup

```bash
cd backend
uv sync --dev
```

When local transcription is configured, Demo media reconciliation enqueues every
registered Completed Media Asset of the Event, regardless of Session association.
It drains the registration backlog in batches of up to 500, oldest first. Operation
identity is scoped to Event, asset, manifest revision and execution profile; the
Session-scoped trigger reuses existing operations, including old Session-keyed work.
Worker retries stay on the same operation; terminal failures are not automatically
re-enqueued. Suggestion runs can use an unassociated asset's latest complete transcript
reference. See [trigger scope and replay](../docs/architecture/transcription-evidence-readiness.md#trigger-scope-and-replay).

Local transcription is an optional, operator-installed capability: an operator can
explicitly install it locally with `uv sync --group transcription`. Under ED-0075, the
`transcription` group and its runtime dependencies must be excluded from every
distributable StageFlow artifact because the confirmed PyAV wheel bundles a GPL-configured
FFmpeg build. Do not promote these dependencies into the default installation or use
`--all-groups` for distribution. This defers rather than resolves the licensing question
and is not legal clearance. See the
[SBOM decision record](../docs/security/dependency-license-sbom-2026-08-21.md#decision-options-for-the-pyavffmpeg-exposure).

## Run the Backend

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Then visit:

```text
http://127.0.0.1:8000/api/v1/health
```

## Quality Commands

```bash
cd backend
uv run pytest
uv run ruff check .
uv run pyright
```

## Architecture Rules

Dependency direction:

```text
api
↓
contexts
↓
shared
↓
core
```

Lower layers must not import from higher layers. ED-0002 creates the physical package boundaries but does not implement StageFlow domain behavior.

## What Belongs Here

- Backend application code approved by Engineering Directives.
- Backend tests.
- Backend-specific Python project configuration.
- Minimal framework integration needed to expose approved API boundaries.

## What Does Not Belong Here

- Frontend code.
- Docker configuration.
- Database models or migrations.
- Authentication or authorization implementation.
- Background workers.
- Media processing, transcription, rendering, or integration adapters before future directives approve them.

## Asset transcription availability (ED-0121)

`GET /api/v1/transcription/assets/{asset_id}/status` requires the existing
`X-StageFlow-API-Secret` authentication. It returns `asset_id`, `operation` (null or
`state`, `execution_profile_id`, `execution_profile_version`), `complete_evidence`,
and `partial_evidence`. The operation matches the currently configured profile and
current manifest; evidence flags follow the asset-wide latest-complete rule used by
Session Suggestions. Partial is true only without a complete revision. No transcript
text, words, paths, worker diagnostics, or connection details are exposed.

Unknown assets: 404 `completed_media_asset_not_found`. Missing composition/configuration:
503 `kernel_not_configured` or `local_transcription_not_configured`. Unavailable storage:
503 `postgresql_unavailable`. This endpoint is read-only; no schema/migration or
configuration default changes. See [transcription evidence readiness](../docs/architecture/transcription-evidence-readiness.md#read-only-asset-availability).
