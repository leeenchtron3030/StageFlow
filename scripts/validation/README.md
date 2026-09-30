# Safe local validation controller

## Session Suggestions live replay

`replay_blocks.py` replays local blocks through the normal demo APIs and workers on a
**disposable review Event and demo database**. It uses only the Python standard library
and the existing Session Suggestions evaluator from the backend environment. It does not
access SQL, repositories, or Kernel internals. This is measurement tooling; a completed
replay is not an accuracy pass or an event-readiness claim.

Prerequisites and preparation:

- The operator creates the disposable database and TOML config outside the repository,
  sets `STAGEFLOW_KERNEL_CONFIG_PATH` to it, and supplies `STAGEFLOW_API_SHARED_SECRET`
  through the environment only. The backend and tool must use the same config and secret.
- Configure exactly one Stage, key `main`, with exactly one `[[event.stages.sources]]`
  folder. Enable `[autonomous_event_node]`, `[local_media_timing]`, and
  `[local_media_segmentation]`. Configure the normal operator-installed ffprobe/FFmpeg
  paths and an appropriate `media_reconciliation_interval_seconds`. Install and qualify
  these tools separately; the replay installs nothing.
- From `backend`, bootstrap and sync the review program with
  `uv run --no-sync python -m app.demo.cli bootstrap` and
  `uv run --no-sync python -m app.demo.cli sync-program`, then run
  `uv run --no-sync uvicorn app.main:app`. Use the same environment in each process.
- Use a fresh Event with no discovered, stabilizing, ready, registered or associated media.
  Keep its watched folder empty and exclusively reserved for this replay. Do not run other
  producers, suggestion commands, or media writers against it during measurement.
- Keep the input block directory, watched folder, optional truth JSON, config, and output
  outside the repository. Blocks must be a flat directory of supported regular files,
  ordered lexicographically by case-insensitive filename (use zero-padded ordinals).
  Symlinks, hidden files, subdirectories and unsupported extensions are refused. At most
  1,000 blocks, further limited by the configured source candidate bound, are accepted.

Run from `backend` (angle-bracket values below are placeholders for operator inputs):

```text
uv run --no-sync python ../scripts/validation/replay_blocks.py --blocks <external-block-folder> --source <external-empty-watched-folder> --pace real --run-every 4 --api-base-url http://127.0.0.1:8000 --actor-id <operator-uuid> --truth <external-truth.json>
```

Use `--pace 10` for ten times real time; numeric pace must be at least 1. Without
`--duration-seconds`, the tool probes each block using the configured ffprobe. Supplying
`--duration-seconds 60` uses that duration for every block and bypasses the initial probes
(the real timing worker still performs its normal inspection). `--run-every` defaults to
1. `--timeout-seconds` defaults to 600 for each bounded pipeline phase, and
`--poll-seconds` defaults to 1. Increase the timeout for long blocks or slow machines.
The first block arrives after its duration divided by pace; subsequent deadlines use
cumulative durations from replay start. Pipeline delays do not add another full pacing
sleep: overdue blocks arrive as soon as the preceding pipeline cycle finishes.

The tool copies into `block-NNNNNN.<extension>.partial` in the watched folder, flushes and
closes it, then atomically renames it to the final name. Normal discovery excludes the
`.partial` suffix before extension matching. Files are never removed; a failed copy may
leave a partial file for the operator to inspect. Existing final or partial files are
refused. A rerun needs a fresh disposable Event and empty watched folder.

Before copying, the tool checks config/source agreement, matching Event/deployment/node
identity, backend readiness and automation, waiting boundedly for startup readiness and
tolerating running discovery reconciliations. It polls normal Kernel status for each new
registration and identifies the asset through paginated timing requests (the recent-media
status projection is capped). It posts timing/segmentation requests with the supplied actor
and `confirmed: "confirmed"`, and runs each worker `--once` until all that Event's
operations of the kind succeed. Terminal failure, cancellation, timeout, an unexpected
asset or a mismatched latest suggestion run stops the replay. Every N blocks and after
the last block (without duplicating a final cadence run), it requests a suggestion run,
reads the latest run, and pages its open suggestions. It never confirms Sessions.

Optional truth is a JSON array of 1..1,000 anonymous objects containing only `start` and
`end`, both timezone-aware ISO timestamps, with end after start; maximum file size is
64 MiB. Use the recording's absolute timeline. Truth is sorted chronologically, retaining
duplicates. The first registered block's advisory timing start anchors replay media time;
missing/invalid timing fails the pipeline rather than guessing from the first truth talk.
Use a single continuous recording sequence; pacing concatenates durations and does not
reconstruct unrecorded gaps or overnight breaks. Timing remains advisory and unqualified.

Stdout is sanitized JSON with these fields:

- `error_count`, `blocks_copied`, `blocks_registered`, `blocks_settled`.
- `runs`: one-based `ordinal`, `blocks_copied`, monotonic `wall_seconds`,
  `media_seconds` (= wall seconds multiplied by pace, including pipeline delay),
  `suggestion_count`, and the closed numeric `skips` counters from the latest run.
- With truth, `talks`: one-based chronological `ordinal`,
  `time_to_first_suggestion_seconds` (= media elapsed at the first matching run minus
  the truth end relative to the recording origin, clamped to zero for early matches;
  null if never matched), `stability_change_count`, and `maximum_edge_move_seconds`.
  Every run uses the evaluator's chronological one-to-one IoU >=0.5 matching, maximizing
  count then minimizing absolute edge error with its existing tie rule. Stability compares
  each later match with the previous match for that truth talk, retaining it across absent
  runs. A run counts once if either edge moves **more than** 1 s; maximum movement is the
  largest absolute start/end change, including changes at or below 1 s. Disappearance
  alone is not an edge change. Zero changes/maximum means no observed movement, including
  never-matched talks; consult latency and final recall alongside stability.
- With truth, `final_accuracy`: truth/suggestion/matched counts, recall, and median
  start/end errors from `evaluate_accuracy` on the last completed run. No completed run
  yields zero matches and null errors. Partial reports use completed runs only.

Exit codes: **0** completed (irrespective of measured accuracy), **1** invalid input or
pre-copy safety refusal with only `{"error_count": 1}`, **3** pipeline failure/timeout with
a sanitized partial report. `--help` exits 0. The optional Markdown form is not emitted;
JSON is the report format. Paths, filenames, titles, IDs, absolute timestamps, DSNs,
secrets, raw API dictionaries and child-process diagnostics are never emitted. The secret
has no CLI option; HTTP sends it only in `X-StageFlow-API-Secret`, with redirects refused.
Keep raw inputs and shell history private, and review sanitized output before publishing.

`backend/tests/test_validation_replay_blocks.py` uses fake HTTP, subprocess, copy, clock
and sleep effects; no real database, network, FFmpeg or media is required. The separate
owner-run synthetic-day replay supplies qualification evidence.

## Existing validation controller

`Invoke-StageFlowValidation.ps1` is a thin, non-production PowerShell controller for
the existing `backend/tests/qualification/real_event_playback.py` runner. It derives a
Run-specific external workspace, performs conservative operator checks, and delegates
every Kernel action to that runner. It does not create a PostgreSQL database, control
vMix, watch directories, schedule work, or implement application/domain behavior.

The controller is under `scripts/` because that directory is the repository's existing
home for developer utilities. Run it from any working directory.

## Prerequisites and safety boundary

- Windows PowerShell 5.1 or PowerShell 7;
- `uv` and Git available locally;
- `psql` on `PATH` or under a conventional Windows PostgreSQL installation directory;
- an operator-created, disposable database named `stageflow_validation_NNN` for Run
  `NNN`;
- the matching DSN in `STAGEFLOW_VALIDATION_DSN`; and
- an external root whose path contains a `stageflow-validation` directory.

When `STAGEFLOW_VALIDATION_ROOT` is unset, the root defaults to
`<Desktop>/StageFlow/stageflow-validation`. Run 004 therefore derives:

```text
stageflow-validation/
  kernel-run-004.toml
  run-004.json
  run-004.md
  run-004.environment.json
  run-004.operation.lock
  run-004.operation.lock.json
  media/
    run-004/
```

The environment manifest records redacted setup evidence such as Git commit/dirty
state, tool versions, PostgreSQL server version, OS, cadence, and external paths. It
never stores a DSN or credential value.

The controller:

- refuses Run 001 and Run 002, protecting the accepted baseline artifacts;
- refuses a validation root inside the repository;
- requires the database name, Event key, deployment identity, source directory, run
  record, and Run number to agree;
- refuses to overwrite an existing Run configuration, result, summary, environment
  manifest, or non-empty media directory;
- probes the already-created database before `Prepare` writes anything;
- takes a host-local exclusive lock for each Run before a mutating controller/runner
  operation and refuses overlap while either the controller or its child still owns a
  lock region;
- uses exactly one Stage (`main`) and one `.mp4` source;
- requires explicit `-ConfirmHumanAuthority` for Session boundaries, manual assignment,
  Package Ready, and package completion;
- refreshes status before Package Ready and rejects active, unavailable, stale/recovering
  state;
- requires explicit review when stabilizing, unresolved, conflicting, or attention
  state remains, without changing the application's package semantics; and
- propagates the qualification runner's non-zero exit code.

The controller intentionally provides no `Force` or database-creation option. If
`Prepare` stops after creating some matching artifacts, inspect them and resume only
with the explicit `Initialize`, `Migrate`, `Bootstrap`, or `Status` action that remains
necessary.
Never delete or reuse an earlier Run to make preparation pass.

## Action map

| Controller action | Existing runner command | Additional controller behavior |
| --- | --- | --- |
| `Prepare` | `initialize`, `migrate`, `bootstrap`, `status` | Generates external TOML/metadata after tool and database preflight; refuses overwrite |
| `Status` / `Checkpoint` | `status` | Prints a concise Kernel, Stage, Session, media, package, and attention summary |
| `Status -Offline` | none | Interprets the last recorded snapshot without database access or changing the record |
| `Reconcile` | `reconcile` | Runs explicit supported reconciliation, then summarizes status |
| `Expectation` | `expectation` | Records external Program expectation context |
| `StartSession` | `start-session` | Requires explicit human-authority confirmation; captures `-At now` at controller entry and forwards an explicit aware timestamp |
| `EndSession` | `end-session` | Requires explicit human-authority confirmation and a reason; captures `-At now` at controller entry and forwards an explicit aware timestamp |
| `Cycle` | `cycle` | One bounded media cycle |
| `DriveCycles` | `drive-cycles` | Finite sequential cycles; cadence remains start-to-start; oversized interactive batches are refused with a smaller suggested bound |
| `AssignAsset` | `assign-asset` | Requires attributable human confirmation, asset ID, Session label, and reason |
| `PackageReady` | `status`, then `package-ready` | Verifies authoritative Presentation End and fresh readiness first |
| `CompletePackage` | `complete-package` | Requires an explicit approve/reject decision and reason |
| `RecordStop` | `record-stop` | Records an operator stop without stopping any process |
| `Reconstruct` | `reconstruct` | Uses the runner's fresh-process reconstruction path |
| `Initialize` / `Migrate` / `Bootstrap` | same-named command | Explicit recovery actions after a matching partial preparation |
| `ShowPaths` | none | Displays canonical Run paths and identities without reading the database |

Use `-DryRun` to inspect safe command construction without writing files or invoking the
runner. A dry run still validates the Run/database name and, for an existing Run,
matching external artifacts. It never displays the DSN.

## Same-Stage turnover qualification workflow

Run 003 is preserved as **INVALID — intended same-Stage turnover qualification not
executed**. Its secondary finding is **PASS — media-without-Session-authority
preservation/conservatism diagnostic**. Do not reuse or repair its external artifacts.
Run 004 later completed as a partial qualification; its preserved result is indexed under
`docs/validation/results/`. Use a fresh Run number and workspace for another experiment.

During recording, all human-authority declarations go to the Codex execution
conversation. ChatGPT web is used before the run for experiment design and after the run
for interpretation.

The controller resolves `-At now` for StartSession and EndSession immediately after
PowerShell parameter binding, before authority guards, configuration reads, runner
startup, or other controller work. It then forwards the resulting timezone-aware ISO
timestamp unchanged. An explicit `-At <aware-ISO-timestamp>` remains unchanged.

The controller invocation must be the qualification agent's first action after receiving
the live declaration. Reasoning, checkpoints, or other commands must not occur first:

```text
human declares boundary
  -> invoke controller immediately; controller captures timestamp
  -> guards and runner execution
  -> Kernel receives the captured explicit timestamp
```

This prevents controller/runner latency from becoming Session occurrence time. It does
not make Codex message-delivery latency or a future UI interaction part of the Kernel.
A product control surface must preserve its accepted occurrence timestamp independently
of downstream processing and commit latency.

Prepare and checkpoint the fresh isolated Run 004 before creating expectations or
realizing Sessions:

```powershell
$env:STAGEFLOW_VALIDATION_DSN = "<DSN for stageflow_validation_004>"
$controller = ".\scripts\validation\Invoke-StageFlowValidation.ps1"

& $controller -Run 4 -Action Prepare
& $controller -Run 4 -Action Checkpoint
```

Record optional external expectations, then realize Session A with the opt-in turnover
guard. Session labels are local runner handles; they do not change StageFlow Session
identity. A successful guarded start prints exactly `SESSION A ACTIVE — SAFE TO BEGIN
RECORDING` before the operator begins recording.

```powershell
& $controller -Run 4 -Action Expectation -ExpectationKey "session-a" -Title "Session A"
& $controller -Run 4 -Action StartSession -SessionLabel "session-a" `
  -ExpectationKey "session-a" -ConfirmHumanAuthority `
  -TurnoverGuard -TurnoverPhase SessionA
& $controller -Run 4 -Action DriveCycles -SessionLabel "session-a" `
  -Scope "validation-session-a" -CycleEverySeconds 2 -MaxCycles 7 `
  -TurnoverGuard -TurnoverPhase SessionA
```

Before every guarded `DriveCycles`, the controller prints the expected Session label and
current authority state. It refuses unless that Session is `presentation_active`,
prominently prints `WAITING FOR HUMAN AUTHORITY — DO NOT CONTINUE MEDIA PROCEDURE`, and
does not invoke the runner. Generic unguarded Sessionless ingest remains supported.

At the selected boundary, declare Session A ended. Success prints exactly `SESSION A
ENDED — KEEP RECORDING; WAITING FOR SESSION B AUTHORITY`. Start Session B on the same
`main` Stage while Session A's package remains assembling. Session B start requires
Session A to be `presentation_ended` with a non-null authoritative end; it does not
require Session A Package Ready or Complete. Success prints exactly `SESSION B ACTIVE —
SAFE TO CONTINUE TURNOVER INGEST`.

```powershell
& $controller -Run 4 -Action EndSession -SessionLabel "session-a" `
  -At now -Reason "human_confirmed_substantive_end" -ConfirmHumanAuthority `
  -TurnoverGuard -TurnoverPhase SessionA
& $controller -Run 4 -Action Expectation -ExpectationKey "session-b" -Title "Session B"
& $controller -Run 4 -Action StartSession -SessionLabel "session-b" `
  -ExpectationKey "session-b" -ConfirmHumanAuthority `
  -TurnoverGuard -TurnoverPhase SessionB -PredecessorSessionLabel "session-a"
& $controller -Run 4 -Action DriveCycles -SessionLabel "session-b" `
  -Scope "validation-session-b" -CycleEverySeconds 2 -MaxCycles 7 `
  -TurnoverGuard -TurnoverPhase SessionB -PredecessorSessionLabel "session-a"
```

After Session B ends, the guarded command prints exactly `SESSION B ENDED — SAFE TO STOP
RECORDING`. Stop recording, then run a deliberately bounded unguarded trailing
stabilization batch if that is part of the approved procedure. The turnover guard is not
used after authoritative end because guarded ingest requires an active Session. Do not
translate stabilizing or ambiguous media into a production failure.

```powershell
& $controller -Run 4 -Action EndSession -SessionLabel "session-b" `
  -At now -Reason "human_confirmed_substantive_end" -ConfirmHumanAuthority `
  -TurnoverGuard -TurnoverPhase SessionB -PredecessorSessionLabel "session-a"
& $controller -Run 4 -Action DriveCycles -Scope "validation-trailing-media" `
  -CycleEverySeconds 2 -MaxCycles 7
& $controller -Run 4 -Action Checkpoint
```

The controller estimates interactive duration as qualification telemetry using the
larger of durable observed media count and a metadata-only count of currently eligible
entries in the configured shallow source. Source counting uses configured extensions,
excludes hidden names and `.partial`/`.tmp` suffixes, skips directories and reparse
points, and stops at the configured inspection bound; it never opens or processes media.
The empirical model remains `0.502 + 0.313 × effective Candidate count` seconds per core
cycle plus cadence and conservative overhead. The controller refuses a batch approaching
`-InteractiveExecutionBudgetSeconds` (default 180), suggests a smaller finite maximum,
and never silently changes the requested cycle count. This is not a production SLA.

If the Codex/host wait times out, do not assume the child terminated. A surviving runner
keeps its Run lock region, and later mutating actions refuse with the safely available
action/PID/start diagnostic. Wait for or independently check the child before continuing;
do not launch reconciliation or checkpoint concurrently.

Use `AssignAsset` only for a deliberately reviewed correction. Once each Session has an
authoritative end and its membership/attention state has been reviewed, transition and
complete each package independently:

```powershell
& $controller -Run 4 -Action PackageReady -SessionLabel "session-a" `
  -ConfirmHumanAuthority
& $controller -Run 4 -Action CompletePackage -SessionLabel "session-a" `
  -Decision Approve -Reason "human_reviewed_validation_membership" `
  -ConfirmHumanAuthority

& $controller -Run 4 -Action PackageReady -SessionLabel "session-b" `
  -ConfirmHumanAuthority
& $controller -Run 4 -Action CompletePackage -SessionLabel "session-b" `
  -Decision Approve -Reason "human_reviewed_validation_membership" `
  -ConfirmHumanAuthority
```

If the checkpoint still reports stabilizing, unresolved, conflicting, or attention
state, inspect the raw external record first. `-ConfirmAttentionReviewed` acknowledges
that review for `PackageReady`; it does not resolve media, waive an application guard,
or create a new domain rule. The current accepted Kernel permits an empty package after
authoritative Presentation End, so the controller does not add a non-empty-membership
requirement.

Finish with a recorded stop and supported reconstruction:

```powershell
& $controller -Run 4 -Action RecordStop -At now `
  -Reason "fresh_process_reconstruction_check"
& $controller -Run 4 -Action Reconstruct
& $controller -Run 4 -Action Checkpoint
```

The full measurement definitions, same-Stage acceptance criteria, and result-recording
procedure remain authoritative in
[`docs/plans/real-event-playback-validation.md`](../../docs/plans/real-event-playback-validation.md).

## Current limitations

- The controller is intentionally local PowerShell qualification tooling, not a Producer
  control surface.
- `psql` preflight supports a standard `postgres://` or `postgresql://` URI and local
  connection parameters; unusual DSN/query-option workflows should continue using the
  runner directly after equivalent operator verification.
- Commands remain sequential and operator-driven. The per-Run byte-range lock is
  host-local qualification protection, not a production distributed lock; noncooperating
  external writers are detected optimistically at save time but cannot be coordinated.
- JSON run-record replacement is atomic and fingerprint-checked. Completed `DriveCycles`
  evidence is checkpointed after each cycle; Markdown is a derived companion and is
  written after the authoritative JSON.
- The controller summarizes bounded runner projections. The external JSON/Markdown
  record remains the detailed evidence source.
- Database provisioning, vMix recording configuration, media rights, machine power,
  source availability, and experiment timing remain operator responsibilities.
