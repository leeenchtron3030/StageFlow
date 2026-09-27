# Production media timing inspection - Host validation Run 001

## Status and authority boundary

**PASSED - The ED-0090 media timing worker inspected every registered live-run recording on
the reference host with the operator-installed LGPL `ffprobe`.**

- It recorded advisory, `unqualified` Media Timing Evidence through the existing ADR-0027
  application boundary.
- The Derived candidate intervals reproduce the vMix reconnaissance: aware UTC starts
  exactly 60 s apart.
- No Kernel fact changed.

This is the owner's host step for ED-0090 under
[ADR-0033](../../adr/ADR-0033-production-media-timing-inspection.md) and the
[approved plan](../../plans/production-media-timing-inspection.md) (in-scope item 10).

- It does **not** qualify the recorder profile.
- It does not establish that `creation_time` marks content start.
- It is not evidence of Event readiness.

No media path, filename, username, connection string, or tool output is recorded here.

## Setup

- **Host and tool:** the reference host of the render runs, with the LGPL FFmpeg 8.1.2
  build's `ffprobe`. It was supplied by explicit path in an optional `[local_media_timing]`
  section and identified by version and SHA-256.
- **Database:** the local demo database, backed up with `pg_dump` first, then migrated
  forward to `0017`.
- **Code:** branch `codex/ed-0090-media-timing-inspection` (Phase A `a84fa99`, Phase B
  `6fdde32`).
- **Scope:** the 2026-08-26 live-run Event, whose registered assets were queued through
  the human-only backfill command (`enqueue_existing`, authority `human`, confirmed).

## Results

| Check | Result |
| --- | --- |
| Operations | 12 `media_timing` operations for 12 registered assets; all `succeeded` |
| Worker wall time | 11 assets in about 45 s over eight `--once` cycles at concurrency 2; the 12th in about 11 s |
| Evidence | one revision per asset; recorder qualification `unqualified` on all |
| Derived intervals (rule `creation_time_plus_duration` v1) | eleven blocks starting at 14:46:15 UTC, **each exactly 60.0 s after the previous one**; durations 60.011–60.033 s, and a final block of 57.429 s |
| Stray file in the source folder | a separate 1.96 s clip recorded on 2026-09-21, inspected with its own `creation_time` |
| Backfill replay | the second backfill returned 12 operations and created only 1 new one: the 11 finished operations came back unchanged |
| Kernel facts | `media_started_at` is still NULL for all 12 live-run assets. No Session, association, membership, or package change. |
| Security review of the branch diff | no finding at confidence 8 or higher. Below-threshold hardening notes: an optional demuxer allowlist, and the existing API pattern of an actor supplied in the request body |

## Observations

- **Registrations during worker startup are not auto-queued.**
  - Starting a Kernel-configured worker runs the existing startup media cycle.
  - In this run, the startup cycle registered the stray clip after the first backfill had
    already queued the other eleven.
  - Only Demo reconciliation queues new assets automatically, as ADR-0033 decision 4 and
    the review noted. Assets registered by startup or recovery cycles need the backfill
    command.
  - The same startup cycle had earlier re-registered the recordings folder under the
    ED-0087 validation Event (23 assets there, 11 of them seeded by hand). This existing
    behaviour is harmless.
- **The creation times match the reconnaissance.** They are aware UTC, 60 s apart, and
  consistent with the 60 s segment length. Their meaning (recording start versus the
  instant the file was opened) remains **unqualified**, as ADR-0027 requires.

## Interpretation

StageFlow now has a production, provenance-bearing, advisory source for each file's start
time. For this recorder, it agrees exactly with the earlier qualification-only
reconnaissance. That unblocks the two consumers ADR-0033 names, each in its own directive:
- Assembly ordering by timing evidence, which upgrades the ED-0088 fallback;
- placing derived Editorial candidates on the Session timeline.

Limits:
- a single host, a single recorder, and a single Event;
- no recorder-profile qualification.
