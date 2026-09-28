# Rendering context

The default Render Profile is `h264-nvenc-1080p-video`, version 3: CUDA decode,
H.264 NVENC, preset p4, VBR 8 Mbit/s, GOP 60, 1920 by 1080, MP4,
with constant 30000/1001 video and one native AAC-LC audio stream at 48 kHz,
stereo, 192 kbit/s. These video settings are unchanged from v2.

The closed preset catalog also includes `h264-nvenc-1080p-high` v1 (1080p High)
and `h264-nvenc-720p` v1 (720p Compact). Every preset uses the same codecs, frame
rate, GOP, NVENC preset, sample rate, stereo channels and MP4 container.

| Preset | Resolution | Video default; allowed range, 0.5 Mbit/s steps | Audio default; allowed kbit/s |
| --- | --- | --- | --- |
| 1080p Standard | 1920 by 1080 | 8; 6–12 Mbit/s | 192; 128, 160, 192, 256 |
| 1080p High | 1920 by 1080 | 14; 10–20 Mbit/s | 256; 192, 256, 320 |
| 720p Compact | 1280 by 720 | 4; 3–6 Mbit/s | 128; 96, 128, 160, 192 |

Only video/audio bitrate is adjustable. `RenderAdjustments` is immutable and values
equal to preset defaults normalize to null. `effective_profile` resolves the values;
`require_requestable` rejects uncatalogued identities, fixed-property changes and
out-of-bounds effective profiles. Worker and FFmpeg boundaries recheck these facts.

Each resolved input is probed with the operator-installed LGPL ffprobe under the render
demuxer allowlist. Probe errors are typed failures, never assumed silence. Stage 1a encodes
each input's video once, video only, using CUDA decode, scale_cuda and NVENC; its reported
frame count fixes the segment length. Stage 1b copies that video and adds audio of exactly
round(frames x 1001/30000 x 48000) samples: the input's first audio stream, resampled to
48 kHz stereo and anchored at time zero (`aresample=async=1:first_pts=0`), or digital
silence when audio is absent, padded and trimmed by sample count (`apad=whole_len`,
`atrim=end_sample`). It is stored as 16-bit PCM in a temporary MOV. `apad` with `-shortest`
is not used: on FFmpeg 8 it overran each segment's audio by minutes (render validation
Run 003). Stage 2 concatenates these intermediates, copies video and encodes native AAC
once, avoiding per-join AAC priming. Frame count and duration come from stage 2.
ffprobe must confirm exactly one H.264 video and one AAC audio stream before publication;
otherwise the attempt fails with render_output_invalid.

Inputs with more than two audio channels (e.g. 5.1) are down-mixed to stereo by `aformat=channel_layouts=stereo`.

Intermediates are never registered and are removed on success, failure and cancellation.
They use the output store's .tmp directory. Operator note: allow approximately twice the
output size during stage 2, with additional headroom for uncompressed PCM audio. Each
input's video-only file is removed as soon as its audio-fitted copy exists. Abrupt
process termination can leave temp files; these remain unregistered and require operator
cleanup, as with existing temporary outputs. No automatic historical-data deletion occurs.

With no Event setting, new requests default to unadjusted Standard v3. Explicit
Standard v1/v2 requests return render_profile_unsupported
(HTTP 409). RENDER_PROFILE_V1 and RENDER_PROFILE_V2 record video-only historical identities.
Existing outputs and sidecars stay readable without rewriting history.
CURRENT_RENDER_PROFILE names v3; the FIRST_RENDER_PROFILE alias has been removed.

Human quality selections append an Event Render Setting with actor, aware injected-clock
time and command identity. Migration `0020` adds this immutable table and three nullable
operation-input columns; no existing rows, columns, keys, constraints or foreign keys
are rewritten. The capability-owned unique command ID and SHA-256 request digest provide
exact replay; conflicting command reuse is refused. Refusals leave no receipt.
`expected_version` serializes competing selections through an Event-scoped transaction
lock; stale choices return `render_setting_changed` (409). The same lock covers setting
resolution and enqueue. Out-of-range choices return `render_adjustment_out_of_bounds`.

Render confirmations carry `expected_setting_version` (null for the implicit default).
The request freezes preset, normalized adjustments and setting version in the operation.
Optional profile fields must agree. Legacy Standard v3 bodies without an expected version
work at unadjusted Standard; a conflicting adjusted or different preset is refused.
Recorded command replay uses its frozen setting even if current quality has changed,
including after a lost response. New unadjusted requests retain work-key schema v1;
adjusted requests use schema v2 with an adjustments digest. Equal effective settings reuse
the existing operation, retaining its original setting provenance. The command digest
includes the effective settings. Changing quality never alters operations or outputs.

The reverse migration refuses while settings exist or any new input column is non-null.
Back up the deployment database before applying it. With recorded settings, code rollback
keeps the additive schema and history; older code displays adjusted renders as preset
defaults. Worker configuration is unchanged; one worker declares every catalog preset
and claims any matching preset, with one active GPU lease. Sidecars include effective
video/audio bitrates beside profile identity.

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

The unadjusted work key is Assembly revision plus profile ID and version; adjusted
settings also include the adjustments digest. Requesting Standard v3 for a
revision already rendered under v1 or v2 creates a new operation. Exact command replay
returns the existing operation and its current state, including failure or cancellation.
Conflicting command intent fails typed. Another command for the same work returns the
existing operation; generated output tokens do not create new work. Re-rendering the
same revision/profile after terminal failure is outside this slice: a new approved
revision is the supported path. No generation or attempt component is added to the key.

`RenderWorker` declares and claims every catalog preset. Standard v1/v2 operations
remain visible and are never claimed, leased, or attempted by the current worker;
the shared ADR-0025 substrate may still promote a due historical operation from `pending` to
`eligible` as it does for all work.
The worker claims one render lease, renews and fences through the shared ADR-0025
repository, and commits output identity with operation success in one transaction.
Exceptions after `mark_running` become typed attempt outcomes that release the lease;
unexpected exceptions use `render_internal_error` without exception text. An expired
or replaced lease still cannot mutate the current attempt. The transcription worker
also records unexpected post-running exceptions as `transcription_internal_error`,
retryable within the existing attempt limit, with only that bounded code as its
diagnostic. Its previously handled outcomes retain their behavior. Failure recording
remains fenced: lease-loss or storage errors propagate to the caller, without claiming
that the lease was released; expiry reconciliation remains responsible for recovery.

Infrastructure resolves content, verifies packaging hashes and sizes, identifies an
explicit operator-installed FFmpeg binary, rejects GPL/nonfree configurations, and
writes temporary files inside the configured output store before hashing, fsync and
atomic rename. Only opaque keys, hashes and bounded identity fields are persisted.
Stderr remains transient and is never logged or persisted. The CUDA fallback guard
recognizes setup failures; it does not prove hardware decoding of every frame.
The generated concat list uses `-f concat -format_whitelist concat`. Every file entry
then sets `option format_whitelist mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf`.
FFmpeg's [concat reader](https://ffmpeg.org/doxygen/trunk/concatdec_8c_source.html)
copies the parent whitelist before passing per-file open options; those options replace
the inherited value before the demuxer whitelist check. This admits StageFlow's list
while refusing a disguised concat or playlist among its referenced media. Existing
protocol restrictions and path checks still apply.
After a definite result-registration failure (including lease loss, conflict, or storage
failure before commit), both published files are discarded. After an ambiguous database
commit, published files remain for operator reconciliation; they are not automatically
deleted. Only committed Rendered Output identities are exposed as outputs.

The optional `[local_render]` configuration is disabled by default. Launch the separate
worker with `python -m app.demo.render_worker`. It requires the optional
[local_render] ffprobe_path setting; old configuration files remain valid and the API
does not require this setting. The startup refusal names the setting without its value.
The authenticated API exposes
`POST /api/v1/rendering/requests` and bounded Event/Session-scoped
`GET /api/v1/rendering/operations` and `/outputs`. Listings use an opaque ID cursor and
a maximum page size of 100. The execution profile's configured eligibility records
the NVENC probe result; runtime identity carries FFmpeg version and binary SHA-256.
Operation responses include aware ISO `created_at` and `updated_at` from the journal.
The operations API orders by `created_at` descending, then operation ID descending;
the ID cursor resolves its persisted timestamp for chronological keyset pagination.
The repository's default ID order and output listing order remain unchanged.
`GET /api/v1/rendering/presets` exposes the catalog. `GET` and human-confirmed `POST`
`/api/v1/rendering/events/{event_id}/render-setting` read history and choose quality.
Operation and output listings add nullable `video_bit_rate`, `audio_bit_rate`, and
`event_render_setting_version`; null bitrates mean the recorded preset's defaults.

No overlays, publication, delivery, automatic authority or repository FFmpeg dependency
is introduced. The Event page summarizes quality, offers bounded choices with a
consequence-first confirmation, and collapses prior settings. Session confirmations name
the current quality; a mismatch with the latest output exposes one explicit re-render
action. Standard v1/v2 history retains its video-only label. Owner UX review and GPU
Run 004 remain separate qualification steps. Host GPU/playability qualification and the dedicated
security review remain owner steps; contract tests are not event-readiness evidence.
