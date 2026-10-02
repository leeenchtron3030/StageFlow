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

## GPL-free default transcription (ED-0123)

Transcription is GPL-free and part of the default install under ADR-0036. Default
Python dependencies include CTranslate2 4.8.1, tokenizers 0.23.1, and NumPy 2.5.2.
The default provider is `stageflow-ctranslate2-whisper`, with CUDA/float16 and profile
`ct2-whisper-large-v3-turbo-cuda-float16` version `1.0`. Provision the large-v3-turbo
model, LGPL FFmpeg/ffprobe binaries and CUDA runtime locally; there are no downloads
at execution time. The legacy engine and both transcription dependency groups are removed.

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

`tokenizer.json` is required in the model directory. If `[local_transcription].ffmpeg_path`
is absent, it inherits `[local_media_segmentation].ffmpeg_path`. Without either path,
configuration fails with `local_transcription_ffmpeg_path_required`; an invalid explicit
path is refused, never replaced. An LGPL `ffprobe` executable must be alongside FFmpeg.
Demo preflight checks the model/tokenizer, FFmpeg file and CTranslate2 inference import
with closed codes `local_transcription_model_unavailable`,
`local_transcription_ffmpeg_unavailable`, and `local_transcription_runtime_unavailable`,
then exercises synthetic inference. No media or model path is printed by those checks.
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

**D6 switching rule:** switch profiles between Events. Engine/device/compute choices
must have distinct profile identities. `provider = "faster-whisper"` is refused with an
actionable migration message naming the new provider; it is never silently remapped.
Every profile id starting with `faster-whisper` is also refused. Keep an existing Event's
profile throughout its life where possible. A deliberate profile change on an existing
Event re-transcribes every registered asset under ED-0120; previous transcripts remain
readable, immutable evidence carrying their own provider identity. This release cannot
execute pending legacy-profile work; finish it with the prior installation before
upgrading, or deliberately change the Event profile and accept re-transcription.
The owner D5 parity gate passed in [Run 001](../docs/validation/results/transcription-engine-parity-001.md).
This switch does not assert production-event readiness.

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
