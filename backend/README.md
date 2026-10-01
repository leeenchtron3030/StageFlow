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

## Additive CTranslate2 transcription provider (ED-0122)

The optional `transcription-core` group contains CTranslate2 4.8.1, tokenizers 0.23.1,
and NumPy 2.5.2. Provision these and the local large-v3-turbo model offline. The
default remains faster-whisper; the existing `transcription` group and ED-0075
distribution exclusion remain unchanged pending owner parity qualification and ED-0123.

Example operator configuration (paths refer to locally provisioned resources):

```toml
[local_transcription]
provider = "stageflow-ctranslate2-whisper"
model_id = "large-v3-turbo"
model_version = "<provisioned-model-revision>"
model_path = "C:/StageFlowModels/large-v3-turbo"
ffmpeg_path = "C:/StageFlowTools/ffmpeg/bin/ffmpeg.exe"
device = "cuda"
compute_type = "float16"
execution_profile_id = "ct2-whisper-large-v3-turbo-cuda-float16"
execution_profile_version = "1.0"
```

`tokenizer.json` is required in the model directory. The explicit FFmpeg path is
required for this provider; an LGPL `ffprobe` executable must be alongside it.
Both binaries are versioned and hashed, and GPL/nonfree build flags are refused.
Decode averages all 1–8 channels, produces 16 kHz s16 PCM, renews the lease, and has
duration-based output and timeout bounds (maximum input duration four hours).
Inference fixes English, beam 5, word alignment, previous-text conditioning, and
the reference temperature fallback, without VAD, batching, or downloads.
Under ADR-0036 decision 5, an unspecified `requested_language` also means English;
the engine does not auto-detect language. Explicit non-English requests are refused.
Worker startup JSON reports decode/probe tool names, versions and SHA-256 hashes
alongside `device`, `compute_type` and `execution_profile`.

The other supported pair is `device = "cpu"`, `compute_type = "int8"`, with profile
`ct2-whisper-large-v3-turbo-cpu-int8`. Other pairs fail at construction. CPU is an
explicit profile, never an automatic fallback. Demo preflight retains its existing
appliance GPU check; the standalone transcription worker can execute the CPU profile.

**D6 switching rule:** switch profiles between Events. Keep profile identities
distinct for each engine: the StageFlow provider refuses the default
`faster-whisper-large-v3-turbo-cuda-float16` and every id starting with `faster-whisper`.
Set an explicit, distinct `execution_profile_id`. Keep an existing Event's
profile throughout its life. A deliberate mid-Event change causes ED-0120 to
enqueue new transcription for every registered asset; previous transcript evidence
remains immutable. Keep the current profile available when operating older Events.
See the [parity procedure](../scripts/validation/README.md#stageflow-adapter-parity-ed-0122)
before selecting the replacement as a production default.

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
