# Hardening follow-ups (2026-09-27)

## Status

Approved

## Execution authority

- Classification: Green autonomous.
- Authority evidence:
  - On 2026-09-27 the owner asked to "proceed with all follow-ups" left open by ED-0087 to
    ED-0095. They are recorded in the completion records of
    `docs/plans/render-durable-operation.md`,
    `docs/plans/production-media-timing-inspection.md`, and
    `docs/plans/producer-outputs-ui.md`, and in ED-0093's security review.
  - ADR-0025 (failure semantics), ADR-0032, ADR-0033, and the Producer outputs UI plan,
    decision D1 (the frontend trust model).
- Implementation-ready: Yes.
- Required escalation: stop if an item would:
  - change a public contract other than the additive fields named here;
  - add a migration or a dependency;
  - weaken an existing protection;
  - change the transcription outcome of any currently handled path.
- Engineering Directives: **ED-0096** (backend) and **ED-0097** (frontend). The owner
  delegated ED numbering.

## ED-0096: backend hardening

1. **Render operation timestamps.**
   - The rendering operations API adds `created_at` and `updated_at`, taken from the
     existing `work_operation` columns. They are aware ISO strings.
   - The repository listing gains a stable chronological order option: newest
     `created_at` first, with the operation ID as the tie-break.
   - Additive only, with no migration.
2. **Unexpected errors in the transcription worker.**
   - When an unexpected exception (anything other than `TranscriptionExecutionError`)
     happens after an attempt is marked running, the worker records a fenced, typed
     attempt failure and releases the lease immediately.
   - The failure code is the bounded `transcription_internal_error`. It is retryable,
     under the operation's existing retry limits, and no message text is persisted.
   - This mirrors the render worker (ED-0087 decision (c)).
   - Every currently handled path keeps its exact behaviour. Tests prove the new branch
     and that the existing branches are unchanged.
3. **The intermittent test.**
   - Find the root cause of the intermittent failure in
     `tests/test_devcon_session_publish.py::test_devcon_no_body_response_maps_to_bounded_reason_without_retry`
     (the local HTTP server).
   - Make the test deterministic without weakening what it asserts: the no-body
     rejection maps to `devcon_publish_rejected:no_body`, with no retry.
   - Record the cause.
4. **Timing inspection for recordings registered outside Demo reconciliation.**
   - When `[local_media_timing]` is enabled, each reconciliation cycle enqueues timing
     inspection for every registered asset of the Event that lacks a `media_timing`
     operation. This covers assets registered by startup or recovery media cycles.
   - It is bounded per cycle (for example 100) and idempotent by work key. It adds no
     new trigger or process.
   - When the section is disabled, nothing changes.
5. **Media format allowlists.**
   - `ffprobe` inspection and FFmpeg render inputs restrict demuxers to an explicit
     allowlist of the container formats StageFlow accepts, using `-format_whitelist`:
     - MP4 and MOV (`mov,mp4,m4a,3gp,3g2,mj2`);
     - Matroska and WebM;
     - MXF;
     - WAV (inspection only).
   - FFmpeg keeps the concat demuxer for its own list file.
   - This closes the ED-0087 and ED-0090 below-threshold notes about disguised playlist
     or concat inputs.
   - Tests use the fake binaries to assert the arguments. The owner re-runs a real render
     and inspection.

## ED-0097: frontend hardening

1. **Host-header allowlist (DNS rebinding).**
   - A Next.js middleware refuses any request, pages and API routes alike, whose `Host`
     is not an allowed host. The allowed hosts are the loopback aliases (`localhost`,
     `127.0.0.1`, `[::1]`) on the server's own port, plus an optional operator-configured
     `STAGEFLOW_UI_ALLOWED_HOSTS` list of exact `host:port` values.
   - A refused request gets a plain 421 or 403 with no body detail.
   - Static assets follow the same rule.
   - Tests cover allowed aliases, a configured LAN host, a rebinding host, a missing
     Host header, and a port mismatch.
   - Existing proxy and security tests are unchanged.
2. **Unicode table drift test.**
   - `editorial-unicode.ts` records the Unicode version it was generated from.
   - A backend test and a frontend test compare that version with the backend runtime's
     `unicodedata.unidata_version`, and fail with regeneration instructions when they
     differ.
   - The regeneration script is committed as developer tooling. It is not imported by
     production code.
3. **Render operations in time order.**
   - Once ED-0096 exposes timestamps, the render operations table sorts newest first by
     `created_at` and shows a readable time.
   - The "operation times are unavailable" note is removed.

## Out of scope

New capabilities, schema changes, dependency changes, and UI redesign beyond item 3.

## Acceptance criteria

- [ ] ED-0096 items 1–5 pass behaviour tests. The full host backend suite, Ruff, and
  Pyright pass. The owner's real render and inspection still succeed with the format
  allowlists.
- [ ] ED-0097 items 1–3 pass tests. Frontend typecheck, lint, test, and build pass. A live
  check shows a rebinding host refused and loopback aliases allowed.

## Rollback

Revert each directive independently. No data changes.

## Completion record

_(Filled in per directive.)_
