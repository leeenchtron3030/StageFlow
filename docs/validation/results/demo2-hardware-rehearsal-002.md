# Demo 2 hardware rehearsal — Run 002

**Run date:** 2026-09-25
**Directive:** ED-0081 ([plan](../../plans/demo2-generalization.md)); follow-up to ED-0071
([plan](../../plans/demo2-hardware-rehearsal.md), [Run 001](demo2-hardware-rehearsal-001.md))
**Subject:** PR #71 `codex/demo2-autonomous-event-node` at merge commit `9d63290` plus
launcher fix `f48087f`, the Demo 2 Autonomous Event Node generalized onto the
provider-neutral program source
**Topology:** One reference host, offline. There was no second machine, no Producer UI
interaction, no live recorder, and no external provider API.

## Disposition

**ED-0071 CRITERIA 4, 6, AND 7 QUALIFIED.** Together with the seven criteria Run 001
passed, all ten ED-0071 criteria now have passing evidence. Demo 2 is therefore
**promotion-qualified**. Merging PR #71 still requires the owner's explicit approval.

ED-0081 added a second part to criterion 6, a PostgreSQL service outage. That part was
**not exercised live**: the owner chose to skip the outage, which needs an elevated shell.
It is covered by a unit test only.

This is rehearsal evidence from one offline host. It is **not** Event certification,
production readiness, or evidence of two-machine or live-recorder behaviour beyond
Run 001.

## Setup

- **Database.** The Demo database (`stageflow_demo`, at migration `0010`) was first backed
  up in full. Then `main`'s accepted additive migrations `0011`-`0013` were applied in
  place, by owner decision.
  - Verification: the ledger gained exactly those three versions, 13 new tables were
    created empty, and all 33,211 pre-existing data rows were unchanged.
  - The rehearsal used a new Event key, so earlier Demo data was not touched.
- **Configuration.** A white-labelled configuration outside the repository:
  - placeholder identities;
  - `event_mode = "rehearsal"`;
  - a `[local_schedule]` source with one Session, and no `[devcon_read]`;
  - `rehearsal_fault_media_cycle = 12`.
- **Media.** The eleven recorded blocks used by ED-0073/ED-0078 were copied into an empty
  watched folder, 20 seconds apart, by the ED-0081 block-replay helper. Each file was
  written under a temporary name and then renamed.
- **Runtime.** The launcher-owned stack (backend, transcription worker, Producer UI) ran
  under PowerShell 7.6.6. Transcription used faster-whisper large-v3-turbo on CUDA
  float16.
- **Lifecycle commands.** The Session commands (start, end presentation, package ready,
  approve package) were issued through the Demo API as the configured operator. This is
  the same authority path the Producer UI uses; the UI itself was not exercised in this
  run.
- **Observation.**
  - A sanitized 1-second poller of the loopback Kernel status. It records coordinator
    state, owner, cycle counts, and failure codes and times only.
  - Point samples of the controller's durable worker projection.
  - Controller `status` snapshots.

## Results

### Core flow on the provider-neutral source (context, not a re-test)

- `prepare` passed: CUDA inference was available, bootstrap succeeded, and program sync
  reported `provider: local_file` with one expectation.
- A Session was started at 18:36:59Z and linked to that expectation.
- All 11 blocks were registered and associated, with 0 unresolved and 0 conflicting.
- 11 transcription Operations succeeded; 11 of 11 Transcription Evidence records were
  complete, with 0 enqueue failures.
- After the presentation ended, package revision 1 became `ready_for_review`. It was then
  approved at that exact revision and became `complete`.
- Program refresh ran on its own timer throughout, with no failure.

### Criterion 4: worker projection reflects real GPU readiness, capacity, and availability — QUALIFIED

| Sample (UTC) | Condition | State | Available | Capacity | GPU transcription |
| --- | --- | --- | ---: | ---: | --- |
| 18:37:18 | Stack running, before the media load | available | 1 | 1 | ready |
| 18:40–18:41 (`status`) | After 11 transcriptions | available | 1 | 1 | ready |
| 19:06:40 | 5 s after the stack stopped | available | 1 | 1 | ready |
| 19:07:17 | After the worker's presence lease expired | stale | 0 | 0 | unavailable |
| 19:08:06 (`status`) | After the restart | available | 1 | 1 | ready |

The projection followed the real worker without any operator action. It moved to `stale`
with no capacity once the stopped worker's durable presence expired (the lease had about
13 seconds left at the stop). It returned to ready when the worker came back.

**Deviation:** the plan called for stopping only the worker. The launcher treats any
child-process exit as fatal and stops the whole stack, so the worker was stopped through a
full stack stop.

### Criterion 6: ED-0063 safety net proven live — QUALIFIED

The rehearsal fault setting fired once per coordinator process, on the configured media
cycle. It raised an exception type outside the anticipated handled set, so it reached the
ED-0063 catch-all:

| Occurrence | Observation |
| --- | --- |
| First process, 18:30:55Z | The launcher log shows `autonomous_event_node_cycle_failed cycle_kind=media_reconciliation exception_type=LookupError`. The next `status` showed `running` with the failure code `unexpected_cycle_failure` and time retained; media cycles continued (56, 111, 115 at successive snapshots). The transient `degraded` state lasted less than one 5 s cycle, so this snapshot did not capture it. |
| After the restart, 19:09:47Z | The 1-second poller captured the sequence: `degraded`, `owner=True`, `media_last_failure_code=unexpected_cycle_failure`, failure time 19:09:47.4Z. Nine seconds later (19:09:57) the state was `running` again after the next successful media cycle, with the failure code and time still visible and cycles advancing. |

The coordinator never stopped. The status was visibly `degraded` with a bounded failure
code, and it recovered through the ED-0081 per-kind recovery. That satisfies ED-0071
criterion 6 as written, and it exercises the ED-0063 catch-all itself, which Run 001 could
not.

**Not exercised live:** the ED-0081 PostgreSQL service outage (`degraded` /
`postgresql_unavailable`, then recovery). The owner skipped it because stopping the
service needs an elevated shell. The outer-loop path is covered by the unit test
`test_outer_loop_recovers_postgresql_ownership_without_clearing_cycle_faults`.

### Criterion 7: restart reconstruction from durable state — QUALIFIED

The launcher-owned stack was stopped at 19:06:35Z. Ports 8000 and 3000 were confirmed
closed, and the stack was restarted at 19:07:23Z. The backend was healthy by 19:07:55Z.
Controller `status` before the stop and after the restart:

| Field | Before stop | After restart |
| --- | --- | --- |
| Session | same ID, `presentation_ended` | same ID, `presentation_ended` |
| Package | `complete`, revision 1, approved | `complete`, revision 1, approved |
| Media | 11 registered, 11 associated, 0 unresolved or conflicting | identical |
| Operations / terminal failures | 11 succeeded / 0 | identical |
| Transcription Evidence | 11/11 complete | identical |
| Worker projection | available, 1/1, ready | available, 1/1, ready |
| Coordinator | `running`, `owner=True` | `running`, `owner=True` (lock re-acquired) |

- The first eight status lines are byte-identical before and after the restart.
- Cycle counters restarted from zero, because they are held in the process.
- No transcription work was re-enqueued after the restart (`total=0`), so nothing was
  duplicated.
- Program refresh ran immediately after the lock was re-acquired.

### Clean shutdown

The stack was stopped through the controller, and ports 8000 and 3000 were confirmed
closed. No external write occurred, and no provider API was called.

## Findings recorded (not blocking)

1. **The launcher needs PowerShell 7.3+.** It passes the launch context with
   `Start-Process -Environment` and generates it with `RandomNumberGenerator.Fill`. On a
   host with only Windows PowerShell 5.1 it failed with opaque errors.
   - Fixed in `f48087f`: `#Requires -Version 7.3`, a README note, and a Windows-only test.
   - PowerShell 7.6.6 was installed on the reference host with winget, by owner decision.
2. **Legacy provider-named fields in operator output.** The `preflight` JSON still reports
   `devcon_program_items` and `devcon_read_available`, and `status` reads `payload.devcon.*`.
   These are unchanged public field names (ED-0079/ED-0080 kept API fields). A future
   white-label pass may alias them.
3. **Mixed time zones in `status`.** The controller prints media and program timestamps in
   different time zones (host local and UTC). This is cosmetic.
4. **Fault-kind tracking and outer-loop recovery.** A fault kind recorded before a
   PostgreSQL outage survives the outer-loop recovery. The review accepted this as
   intended ("outer-loop recovery unchanged").

## Limits

- One host, one offline rehearsal, one replayed eleven-block corpus, one Session.
- There was no live recorder, no second machine, and no Producer UI interaction; those
  were covered by Run 001.
- The replay copies files faster than real time. That is sufficient for these host-side
  criteria, but it is not a recorder-timing qualification.
- The fault setting simulates an unanticipated exception. It does not reproduce any
  specific real-world fault.

## External sanitized evidence hashes

Evidence stays outside the repository.

| Artifact | SHA-256 |
| --- | --- |
| 1 s coordinator status poll (CSV) | 3a13cbbe1be20e5765d18450ecf904f01d23adea12cef7c68ee08a8f85329ffc |
| Durable worker-projection samples (JSONL) | 882430c5436626993060810338196322a1e4f21a37d58c272839fc8de509b726 |
| Controller status before stop | 695f76adb755d9c7be94e7650e4b68cf911fd5a5208343c0df15905d86b2b881 |
| Controller status after restart | 363b5e03a08fa4b268aa9d9e95fcdcc64efde9c663260cac2dd678aa94510ce5 |
