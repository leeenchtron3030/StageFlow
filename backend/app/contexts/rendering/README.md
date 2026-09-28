# Rendering context

The current Render Profile is `h264-nvenc-1080p-video`, version 3: CUDA decode,
H.264 NVENC, preset p4, VBR 8 Mbit/s, GOP 60, 1920 by 1080, MP4,
with constant 30000/1001 video and one native AAC-LC audio stream at 48 kHz,
stereo, 192 kbit/s. These video settings are unchanged from v2.

Each resolved input is probed with the operator-installed LGPL ffprobe under the render
demuxer allowlist. Probe errors are typed failures, never assumed silence. Each input is
encoded once using CUDA decode, scale_cuda and NVENC. Its first audio stream is resampled
to 48 kHz stereo, or digital silence is supplied when audio is absent. Audio is padded
and trimmed to the segment video with apad and -shortest, and stored as 16-bit PCM in a
temporary MOV. The second stage concatenates these intermediates, copies video and encodes
native AAC once, avoiding per-join AAC priming. Frame count and duration come from stage 2.
ffprobe must confirm exactly one H.264 video and one AAC audio stream before publication;
otherwise the attempt fails with render_output_invalid.

Inputs with more than two audio channels (e.g. 5.1) are down-mixed to stereo by `aformat=channel_layouts=stereo`.

Intermediates are never registered and are removed on success, failure and cancellation.
They use the output store's .tmp directory. Operator note: allow approximately twice the
output size during stage 2, with additional headroom for uncompressed PCM audio. Abrupt
process termination can leave temp files; these remain unregistered and require operator
cleanup, as with existing temporary outputs. No automatic historical-data deletion occurs.

New requests default to v3; explicit v1/v2 requests return render_profile_unsupported
(HTTP 409). RENDER_PROFILE_V1 and RENDER_PROFILE_V2 record video-only historical identities.
Existing outputs and sidecars stay readable without rewriting history.
CURRENT_RENDER_PROFILE names v3; the FIRST_RENDER_PROFILE alias has been removed.

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

The work key is Assembly revision plus profile ID and version. Requesting v3 for a
revision already rendered under v1 or v2 creates a new operation. Exact command replay
returns the existing operation and its current state, including failure or cancellation.
Conflicting command intent fails typed. Another command for the same work returns the
existing operation; generated output tokens do not create new work. Re-rendering the
same revision/profile after terminal failure is outside this slice: a new approved
revision is the supported path. No generation or attempt component is added to the key.

`RenderWorker` declares and claims only v3. v1/v2 operations remain visible and are never
claimed, leased, or attempted by a v3 worker;
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

No overlays, publication, delivery, automatic authority or repository FFmpeg dependency
is introduced. The Producer requests v3 and labels it "1080p with audio (v3)"; v1/v2
history retains its video-only label. Host GPU/playability qualification and the dedicated
security review remain owner steps; contract tests are not event-readiness evidence.
