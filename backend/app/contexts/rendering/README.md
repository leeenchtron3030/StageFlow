# Rendering context

The current Render Profile is `h264-nvenc-1080p-video`, version `2`: CUDA decode,
H.264 NVENC, preset p4, VBR 8 Mbit/s, GOP 60, 1920 by 1080, MP4, video only,
with a constant output frame rate of 30000/1001. FFmpeg uses `-fps_mode cfr -r 30000/1001`
after the existing CUDA scale filter, keeping frames on the GPU path. Frame-count
parsing and the CUDA-decode fallback guard are unchanged.

New requests default to v2; explicit v1 requests return `render_profile_unsupported`
(HTTP 409). `RENDER_PROFILE_V1` records the former passthrough identity only. Existing
v1 outputs and sidecar identities remain readable without rewriting stored history.
`CURRENT_RENDER_PROFILE` names v2; `FIRST_RENDER_PROFILE` is a compatibility alias for
it, used only by tests, and may be removed once they adopt the current-profile name.

The pure planner expands frozen Assembly bindings in template slot order: each bound
video Packaging Asset contributes its input, and each `session_media` slot expands
the pinned completion membership in its stored position order. For example, intro,
Session media, and outro retain that order. The planner never re-sorts members or
requires media start timing. ED-0088 freezes each member's `order_source` and aware
`order_key_at` at proposal: known media timing, otherwise registry registration time,
then asset ID for ties. Human approval confirms this order. Legacy untimed invalid
revisions remain readable with a null key and cannot be approved or rendered.
Non-video Packaging Assets produce
`render_input_not_video`; they are never silently skipped. Metadata and override
provenance come from the revision's frozen snapshot and are stored in a sidecar.

`RenderingService.request_render` requires human authority and an approved, non-stale
revision. Staleness uses Assembly's existing predicate: package revision, bound
Packaging Asset approval, and governing metadata overrides. Program refresh alone
does not make a revision stale. PostgreSQL validates new requests in the enqueue
transaction while holding the same Session and Packaging locks as Assembly commands.

The work key is Assembly revision plus profile ID and version. Requesting v2 for a
revision already rendered under v1 creates a new operation. Exact command replay
returns the existing operation and its current state, including failure or cancellation.
Conflicting command intent fails typed. Another command for the same work returns the
existing operation; generated output tokens do not create new work. Re-rendering the
same revision/profile after terminal failure is outside this slice: a new approved
revision is the supported path. No generation or attempt component is added to the key.

`RenderWorker` declares and claims only v2. v1 operations remain visible and are never claimed, leased, or attempted by a v2 worker;
the shared ADR-0025 substrate may still promote a due v1 operation from `pending` to
`eligible` as it does for all work.
The worker claims one render lease, renews and fences through the shared ADR-0025
repository, and commits output identity with operation success in one transaction.
Exceptions after `mark_running` become typed attempt outcomes that release the lease;
unexpected exceptions use `render_internal_error` without exception text. An expired
or replaced lease still cannot mutate the current attempt. Transcription execution is
unchanged; its existing worker only catches its declared execution-error type.

Infrastructure resolves content, verifies packaging hashes and sizes, identifies an
explicit operator-installed FFmpeg binary, rejects GPL/nonfree configurations, and
writes temporary files inside the configured output store before hashing, fsync and
atomic rename. Only opaque keys, hashes and bounded identity fields are persisted.
Stderr remains transient and is never logged or persisted. The CUDA fallback guard
recognizes setup failures; it does not prove hardware decoding of every frame.
After a definite result-registration failure (including lease loss, conflict, or storage
failure before commit), both published files are discarded. After an ambiguous database
commit, published files remain for operator reconciliation; they are not automatically
deleted. Only committed Rendered Output identities are exposed as outputs.

The optional `[local_render]` configuration is disabled by default. Launch the separate
worker with `python -m app.demo.render_worker`. The authenticated API exposes
`POST /api/v1/rendering/requests` and bounded Event/Session-scoped
`GET /api/v1/rendering/operations` and `/outputs`. Listings use an opaque ID cursor and
a maximum page size of 100. The execution profile's configured eligibility records
the NVENC probe result; runtime identity carries FFmpeg version and binary SHA-256.

No audio, overlays, publication, delivery, automatic authority, frontend, or repository
FFmpeg dependency is included. Host GPU/playability qualification and the dedicated
security review remain owner steps; contract tests are not event-readiness evidence.
