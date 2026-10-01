# Safe local validation controller

## Transcription engine spike

`transcription_engine_spike.py` measures the existing path-decoding baseline against
external FFmpeg PCM decoding with the same faster-whisper model (option A), and optionally
a local whisper.cpp CLI (option B). This is offline measurement tooling, authorized by
[the approved plan](../../docs/plans/live-chain-validation.md#decisions-owner-approval-of-this-plan-approves-the-recommended-defaults).
The owner runs it on external blocks and records the result and engine recommendation.
It changes no application behavior, evidence, configuration, or distribution boundary.
Option A still imports faster-whisper/PyAV; it does not qualify a GPL-free package.

Run from `backend`, using the operator-installed transcription environment:

```text
uv run --no-sync python ../scripts/validation/transcription_engine_spike.py --blocks <external-block-folder> --device cuda --language en --profile conference --max-blocks 6 --render-load --markdown
```

Set `STAGEFLOW_KERNEL_CONFIG_PATH` to the existing local TOML file. Only
`[local_transcription]` (`model_path`, `device`, `compute_type`),
`[local_media_segmentation].ffmpeg_path`, and `[local_media_timing].ffprobe_path` are read.
Device/compute defaults match the existing config defaults (`cuda`/`float16`). No server,
database, credentials, or enabled-worker switches are needed. All input paths must be
absolute local paths; binaries must be explicit files, not PATH names or batch wrappers.
The model directory must include `tokenizer.json`: missing tokenizers are refused to
prevent faster-whisper's upstream network fallback. Models and binaries are provisioned
by the operator; the script installs/downloads nothing and reads the config without writing it.
For GPU runs, the operator-provisioned CUDA runtime directory must be on `PATH` before
launching Python, so the native engine can load its CUDA runtime libraries.

The blocks folder and every resolved block must be outside the repository. Use a flat
folder of 1..1,000 regular `.mov`, `.mp4`, `.mkv`, `.mxf`, or `.wav` files. Hidden entries,
symlinks, junction entries, subdirectories, and other extensions are refused. Files are
ordered by case-insensitive filename (case-sensitive tie break); `--max-blocks` selects
the first N, default 6, allowed range 1..1,000. No input file is modified. The operator
supplies the qualified LGPL FFmpeg/ffprobe binaries; this script does not certify licenses.

`--device cpu` overrides only the device, preserving the configured compute type for
both baseline and option A. For CPU measurements, point the environment variable at an
operator-prepared config with a CPU-supported compute type (for example `float32`);
CUDA `float16` may fail on CPU. No automatic precision change hides that difference.
Run CUDA and CPU separately and keep that precision distinction in the owner's external
measurement notes. `--language` accepts only `en`; `--profile` accepts catalog keys and
defaults to `conference`. Default phrases are composed through the existing catalog;
start, end, and changeover phrases are included, deduplicated by normalized tokens.

Engine and timing method:

- **Baseline:** the adapter's lazy model factory is reused. The measurement script mirrors
  `FasterWhisperExecutionAdapter.execute` at
  `backend/app/infrastructure/transcription/faster_whisper.py:273-280`: `beam_size=5`,
  word timestamps enabled, `vad_filter=False`, `condition_on_previous_text=True`, English.
  It passes the media path. A temporary timer around faster-whisper's `decode_audio`
  measures PyAV decode and is restored even on failure. Inference is total minus decode,
  including feature extraction and full consumption of the lazy segment iterator.
- **Option A:** the same model object and settings receive a numpy array. The explicit
  FFmpeg subprocess uses `-map 0:a:0 -vn -ac 1 -ar 16000 -f f32le -`; little-endian
  float32 bytes are copied to an array. Decode time includes subprocess launch and
  byte-to-array conversion. Inference and total use the same timing boundary as baseline.
- **Option B:** supply both `--whisper-cpp-binary <absolute-binary>` and
  `--whisper-cpp-model <absolute-model>`. FFmpeg writes 16 kHz mono `pcm_s16le` WAV into
  private temporary storage outside the repository. The CLI flags are
  `-m <model> -f <wav> -l en -bs 5 -ojf -of <output-prefix> -ml 1000000 -sow`, plus `-ng` for CPU.
  A positive maximum segment text length enables token timing; the high cap avoids
  forcing single-word segments, which would prevent the phrase matcher from finding cues.
  Full JSON token `offsets.from/to` (milliseconds) are required; special tokens are
  discarded and subwords/punctuation merged within each returned segment. Missing or
  invalid token timing fails that engine; segment text/timing is never substituted.
  The operator must supply a CLI supporting these flags and verify its GPU build for
  CUDA runs (the device label is the requested device). Private WAV/JSON scratch is
  removed when the call finishes. Ensure the OS temporary directory is outside the repo.
  Its inference interval includes CLI/model startup and JSON parsing, unlike the reused
  Python model's excluded initial load. Treat this as process-per-block option B latency.

Before measurement, each engine/device performs one untimed inference on one second
of synthetic silence, fully consuming lazy results. For CUDA this is also the runtime
preflight: loading a model alone does not exercise the runtime libraries. Preflight has
a 60-second deadline, including initial model loading. CUDA library/runtime failures
classified by the existing adapter produce `cuda_runtime_unavailable`; other provider,
import, model, or compute-type failures produce `warm_up_failed`. Parent-side worker
spawn failures produce `worker_start_failed`; preflight deadline expiry produces
`warm_up_timeout`. Option B warm-up failures always produce `warm_up_failed`, including
CLI errors and timeouts. These closed codes mark the affected engine's blocks and
produce exit **3**, even if no engine can run; a shared Python model failure on CUDA
excludes both baseline and A. Optional B can still run if the Python engine fails.
Neither preflight nor warm-up contributes samples or timings.

Odd blocks run baseline, A, then optional B; even blocks reverse that order. Both passes
use the same alternation. Immediately before each block's engines run in each pass,
that block is read once in bounded chunks to warm the OS cache; these reads are untimed.
Each row records the closed `first_engine` label and numeric
`engine_ordinal`. Agreement is computed after all engines for that block have finished,
so A/B still compare with baseline when baseline runs last. Probing, cache reads,
worker startup, IPC, warm-up and Python model loading are outside processing timings.
Cache warming is best effort against OS eviction, not a cache-residency guarantee.
The Python model remains resident
during option B, so its GPU memory footprint is part of that comparison's conditions.
Python inference runs in one persistent spawned worker. The parent bounds each measured
call with `--engine-timeout-seconds` (integer seconds, default 300, range 60..14400;
`engine_timeout` on expiry), receives only closed failure codes,
and terminates/reaps the worker on failure or completion. Measurement codes are:

- `decode_failed`: baseline PyAV decode, FFmpeg PCM/WAV decode, or byte-to-array conversion failed.
- `cuda_runtime_unavailable`: the existing adapter classifies a CUDA library/runtime
  failure during Python inference on CUDA, including lazy result consumption.
- `engine_timeout`: the parent measurement deadline or a decoder/engine subprocess timeout expired.
- `engine_failed`: other measurement failures, including invalid provider results;
  unknown worker failure payloads are reduced to this code.

Exception text never crosses the failure IPC boundary or enters the report. Worker
supervision prevents a native library's stalled inference or destructor from holding
the report open indefinitely.
A replacement worker is warmed before measurement. For CPU runs, choose a larger bound
such as `--engine-timeout-seconds 3600`: large-v3-turbo with beam 5 and word timestamps
can take longer than 300 seconds per 10-minute block. Preflight remains 60 seconds.
Python, native CRT descriptors, and Windows OS stdout/stderr handles go to `os.devnull`,
never a diagnostic capture pipe;
the separate private IPC connection carries results and is consumed by the parent.
The worker's FFmpeg decode subprocess timeout is the configured engine deadline minus
10 seconds (290 by default), so it can be reaped before the worker deadline.
Other external measurement subprocesses retain a two-hour
timeout; B's warm-up uses the 60-second deadline. Peak RSS is omitted:
parent lifetime high-water marks would not fairly
compare the subprocess engine. Raw provider output, diagnostics, transcript text, paths,
phrases, titles, config values, and absolute/word timestamps never enter public output.

With `--render-load`, a second pass repeats every engine/block. Each measurement starts
one looping FFmpeg video encode using `-c:v h264_nvenc -f null -`, waits up to 30 seconds
for encoded-frame progress, and stops/reaps that encode afterward, including on engine
failure. It never starts overlapping load processes. Missing NVENC/video or a render
that exits during measurement is `render_load: unavailable`; timings still complete but
are aggregated separately from `active` load. This is a contention probe, not a scheduler
or throughput qualification. The first pass is `render_load: off`.

Stdout is JSON; optional `--markdown` writes a compact aggregate timing table to stderr
so redirected stdout remains parseable JSON. Output contains only ordinals, counts,
seconds, ratios, nulls, and closed engine/device/profile/status/failure labels:

- Per block/engine/pass: media, decode, inference and total seconds, real-time factor
  **media seconds / total processing seconds**, word count, and cue-hit count.
- Word agreement: `difflib.SequenceMatcher` with `autojunk=False` on each word's normalized
  token tuple; matched count and fraction of nonempty baseline words, plus median and
  nearest-rank p95 absolute start/end deltas. Insertions/deletions are unmatched, not
  assigned artificial timing penalties. Punctuation-only words are excluded from alignment.
- Cue agreement: literal Unicode-normalized tokens, as in the existing phrase matcher,
  non-overlapping per phrase and never crossing transcript segments. Hits use the first
  word's start. Chronological one-to-one matching of the same phrase uses an inclusive
  2-second window; reports both hit counts, matched count, baseline-hit fraction, and
  median/p95 absolute timing delta. Changeovers are counted once, not once per role.
- Aggregates: median and nearest-rank p95 of each numeric block metric, grouped by engine,
  pass and render status, with block/sample counts. Nested agreement medians/p95 are
  themselves summarized across blocks, not pooled across all words. Empty comparisons
  are null and excluded from aggregate samples. Failed baselines leave comparison fields
  null while other engines' timings and counts remain available.

Exit codes: **0** completed (including render unavailability); **1** invalid input/refusal,
exactly `{"error_count": 1}`; **3** partial, with completed measurements retained and only
closed `cache_warm_failed`, `probe_failed`, `warm_up_failed`, `cuda_runtime_unavailable`,
`worker_start_failed`, `warm_up_timeout`, `decode_failed`, `engine_timeout`, or `engine_failed` codes.
Engine failures continue to the next engine
and block. No parity pass/fail threshold or engine recommendation is inferred by the tool.
Fake-effect coverage lives in `backend/tests/test_validation_transcription_engine_spike.py`;
these tests require no optional packages, media, FFmpeg, models, GPU, or network.

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
