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
