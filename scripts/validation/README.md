# Safe local validation controller

## StageFlow adapter parity (ED-0122)

`--candidate stageflow` compares an optional operator-installed faster-whisper baseline
with the default `CTranslate2WhisperExecutionAdapter`, including its decode, word timing,
normalization and partial/failure handling. Transcription is GPL-free and part of the
default install under ED-0123; faster-whisper is never a project dependency. The comparison
imports it only at runtime and refuses its absence with `faster_whisper_runtime_unavailable`.
The historical qualification tools in `backend/tests/qualification/` likewise require
an optional operator-installed baseline, local model/tokenizer files and no downloads.
Existing word/cue metrics, alternating
engine order, optional render load, bounded worker deadlines and sanitized reports
are reused. The old option-A spike remains the default mode.
The parity run fixes English for both engines under ADR-0036 decision 5.

```text
uv run --no-sync python ../scripts/validation/transcription_engine_spike.py --candidate stageflow --blocks <external-block-folder> --device cuda --max-blocks 6 --render-load --markdown
uv run --no-sync python ../scripts/validation/transcription_engine_spike.py --candidate stageflow --blocks <external-block-folder> --device cpu --engine-timeout-seconds 3600
```

Provision the optional comparison package in a separate operator environment.
No installation or download is performed by the script. In the operator TOML, set
`[local_transcription].ffmpeg_path` (falling back to `[local_media_segmentation].ffmpeg_path`)
to the LGPL FFmpeg executable, with LGPL ffprobe
alongside it, and `[local_media_timing].ffprobe_path` for the measurement duration
probe. Supply the same offline `model_path` (including `tokenizer.json`) for both.
This mode selects float16 for CUDA and int8 for CPU. Both baseline pairs use the
optional comparison package directly; no legacy production adapter remains.
No live deployment configuration is changed.
Whisper.cpp arguments cannot be combined with this mode. Warm-up consumes synthetic
silence through each engine; partial results are reported as failures, not parity data.

D5 owner evaluation: matched words at least 95% and p95 word-start difference at most
0.6 seconds on every block; over the set, candidate cue hits at least 90% of baseline
hits, and at least 90% of candidate hits matched to baseline. Use per-block cue counts
to compute the totals; the script reports measurements, not an automatic qualification.
Run six or more blocks with and without render load, plus CPU. The owner records the
result and hardware profile. Synthetic automated tests do not replace that gate.

Host-only automated tests use generated unequal-channel stereo audio at 16 kHz and
48 kHz (the latter exercises resampling):
set `STAGEFLOW_TEST_FFMPEG_PATH` and, for CPU inference,
`STAGEFLOW_TEST_WHISPER_MODEL_PATH`, then run
`uv run --no-sync pytest tests/test_ctranslate2_whisper_host.py` from `backend`.
They skip without the operator paths/runtimes. The PCM comparison uses the reference
PyAV decoder and requires agreement within one signed-16-bit step.

## Transcription engine spike

`transcription_engine_spike.py` measures the optional legacy path-decoding baseline against
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

- **Baseline:** an operator-installed `faster_whisper.WhisperModel` is loaded lazily,
  offline-only, with the frozen reference settings: `beam_size=5`,
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

### Opt-in live replay upgrades (ED-0121)

With none of the new options, the existing behavior and JSON keys are unchanged.
`--transcription`, `--arrival growing`, or `--profile-label LABEL` enables the additional
measurements below. `--arrival atomic` is the default. Labels must match
`^[a-z0-9][a-z0-9._-]{0,63}$`; the supplied label is the sole nonnumeric report value
(other than null) and appears only as `profile_label`.

`--transcription` requires `[local_transcription]` in the operator's config, the
default GPL-free engine dependencies, provisioned model/tokenizer files, LGPL FFmpeg and CUDA
runtime libraries on `PATH`, and transcription configured for the disposable Event.
Use distinct profile identities (D6): changing an existing Event profile re-transcribes
its assets; existing transcripts retain their provider identity and remain readable.
Missing both transcription and segmentation FFmpeg paths fails configuration with
`local_transcription_ffmpeg_path_required`. Before arrival, the replay refuses
an existing boundary-cue composition, reads the current catalog, and composes its
Conference stage profile through the human-authority API with a fresh command ID.
After each block's segmentation, it waits for the autonomous node's cumulative enqueue
counter to reach its replay-start baseline plus the block ordinal. It polls the new
asset transcription status endpoint and drives `app.demo.worker --once` while the
operation is nonterminal, with a separate bounded timeout for enqueue and transcription.
The worker's startup line is tolerated, captured stdout is capped at 16 KiB, and only
its allowlisted outcome is parsed; child output is never echoed.

Transcription degrades per ADR-0036: terminal failure, partial-only evidence, or phase
timeout leaves transcript availability null and increments
`transcription_unavailable_count`; partial-only results also increment
`transcription_partial_count`. Replay and suggestion runs continue. Complete evidence
availability is the first observation of `complete_evidence=true`, not merely a
successful worker outcome. Other pipeline/protocol failures retain exit 3 and completed
observations. The status counter baseline is process-local and reported as
`transcription_enqueue_baseline`; a decreasing observed counter is a pipeline failure,
not evidence of new enqueues.

Growing arrival uses one background writer, exclusively creating each final filename
and flushing visible chunks at intervals no longer than one second over duration/pace.
The last chunk targets the original cumulative completion deadline, followed by flush,
fsync, and close. Actual close times anchor stage timings. Disk/scheduler delays can
make a deadline late; subsequent deadlines do not shift. The writer overlaps pipeline
processing, surfaces failures to the main loop, and is stopped/joined on exit; any
incomplete files remain. Discovery's existing stabilization is unchanged. If multiple
assets register while a worker runs, their public timing intervals establish recording
order after timing settles. This uses the existing continuous, chronologically ordered
recording prerequisite and does not depend on the bounded recent-media projection.
Missing timing, duplicate starts, reversed chronology, or registration before a file
closes fails safely. Observed evidence and first subsequent runs are retained for all
known registered blocks, including those that arrived during earlier worker calls.

The additional allowlisted measurements are:

- With truth, each talk adds absolute start/end errors in seconds at `first`,
  `plus_300`, and `plus_900` (fields such as `first_start_error_seconds`). The latter
  select the latest matching observation at or before truth end +300/+900 seconds
  of replay media time, inclusive; no eligible match yields null. Existing matching,
  recording origin, per-talk fields, and `final_accuracy` retain their meaning.
- `stage_timings`: each block's `ordinal` and media seconds from actual close to
  `registered`, `timing`, `segmentation`, `suggestion`, and (when enabled)
  `transcription`. Unobserved stages are null. `stage_summary` contains `median` and
  nearest-rank `p95` for each stage, excluding nulls; no samples yields nulls.
- `evidence_timeline.blocks`: each `ordinal` and media seconds of observed
  `segmentation` and optionally `transcription` availability.
  `evidence_timeline.runs`: run `ordinal`, `media_seconds`, and highest settled block
  ordinal for each evidence kind at that observation (zero if none). A highest ordinal
  does not imply gap-free transcript coverage; consult the per-block nulls.

These are observation times, including polling latency. Driving stages serially means
these timings are a **lower bound on contention**; they do not qualify simultaneous
rendering or appliance capacity.

D4 owner-run protocol: use one day's morning from recording start through lunch, at 1x,
with growing arrival, transcription, and a suggestion run after every block. Use a fresh
Event/source and record the provisional appliance profile, for example append
`--pace real --arrival growing --transcription --run-every 1 --profile-label dev.v1`
to the invocation above. The live policy stays v3. The owner uses the availability
timeline for D5's offline v5 evaluation; this directive performs no real-media run,
policy switch, or held-out-seed evaluation.

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

## Boundary evidence lab (ED-0126, ADR-0038 Phase A)

`derive_ground_truth.py` and `boundary_evidence_lab.py` are offline validation tools.
They fit no model, tune no thresholds against a day, and write no production state.
Their shared `boundary_evidence_*` modules contain only validation effects, numeric
features and reporting. The approved Phase A plan supplies Green execution authority.
No result, readiness claim or completion record is created by installing these tools.

Prerequisites:

- Use the existing backend environment. NumPy and tokenizers are included in
  the default install; no additional dependency is needed. Whisper additionally needs the
  ED-0122 CTranslate2 runtime and an offline-provisioned model with its tokenizer.
- Set `STAGEFLOW_KERNEL_CONFIG_PATH` to the operator TOML. FFmpeg comes from
  `[local_transcription].ffmpeg_path`, falling back to
  `[local_media_segmentation].ffmpeg_path`; ffprobe for ground truth comes from
  `[local_media_timing].ffprobe_path`. Paths are explicit local executables, never PATH
  searches. GPL/nonfree FFmpeg builds and shell wrappers are refused. Tools and model
  weights are never downloaded or bundled. No PyAV or third-party audio/speaker model
  is used.
- Keep media, manifests, truth, graphic PNGs, cue audio, caches and report destinations
  outside the repository. Create the external cache/output parent directories first.
  Relative, UNC and repository paths are refused. Reports cannot alias input files.
- Run with the optional environment installed, for example from `backend` with
  `uv run --no-sync python ../scripts/validation/<tool>.py ...`. The examples below use
  illustrative external paths; substitute private operator paths locally.

### Automatic ground truth

```powershell
uv run --no-sync python ../scripts/validation/derive_ground_truth.py `
  --blocks D:\BoundaryLab\blocks --exports D:\BoundaryLab\exports `
  --intro-skip 8 --outro-skip 5 --threshold 0.8 `
  --join-tolerance 2.0 --acceptance-fraction 0.9 `
  --out D:\BoundaryLab\truth.json
```

Both folders are flat. Exports are sorted by case-insensitive filename (then exact
filename), but names are never emitted. Recorder blocks are placed by timezone-aware
container `creation_time` plus duration, and sorted by that advisory UTC placement.
Consecutive blocks join when the absolute apparent gap or overlap is within
`--join-tolerance` (default 2.0 s), accommodating whole-second recorder timestamps with
fractional durations. Joined samples are anchored continuously to the first block start.
Larger gaps form separate runs; larger overlaps and decoded/container duration
discrepancies greater than 0.1 s are refused. Recorder clock timing remains unqualified,
as in Media Timing Evidence.

The tool decodes 8 kHz mono, subtracts the reference mean, and uses FFT correlation
normalized by each candidate's local centered energy. Five 10 s probes cover start,
early, middle, late and end after stripping the configured intro/outro. Additional
10 s tiles establish source segments using a +/-60 s search around the offset predicted
from the last accepted match. Only the five anchors search globally unconditionally;
a failed local 10 s tile falls back to one global search. Quarter-second sub-tiles
never search globally: they search +/-60 s around the current predicted offset and,
when the parent failed locally, also around that parent's global best match (even
below threshold), advanced by the sub-tile's offset within the parent. Correlation uses
float32 audio and bounded FFT chunks with float64 cumulative energy sums confined to
each chunk.

Tiles are checked in 0.25 s pieces and suspect tiles are rematched at that resolution,
so short cuts still split source segments. Offsets must agree within 0.05 s to form one
segment. A segment is accepted when at least `--acceptance-fraction` (default 0.9) of its
quarter-second tiles meet `--threshold`. Unsupported quiet/processed tiles retain the
predicted placement but never update tracking or count as accepted evidence. This is
waveform matching, not a semantic labeler; up to `1 - acceptance_fraction` (10% by default)
may lack waveform support.
Long corpora still require memory for decoded float32 recording runs, but subsequent
successful tile searches and normalization no longer copy or transform whole runs.

The external JSON array contains `ordinal`, `start`, `end`, `segments`, `min_score`,
`consistent`, `status`, `snippet_scores`, `snippet_aligned`, `acceptance_fraction`
(the configured minimum) and `accepted_fraction` (the measured tile fraction). Each
segment also reports its measured `accepted_fraction`. Times are aware UTC
strings. A failed export has null outer bounds, `status: "unaligned"` and
`consistent: false`; any supported partial segments remain visible. For aligned
exports `min_score` is the minimum tile score, including tolerated unsupported tiles.
Probe scores may be below the threshold when a probe crosses an internal cut; those probes are explicitly unaligned.
For an internally cut export, the outer bounds enclose its first and last source
segments and must not be mistaken for an uninterrupted talk.

Replay/harness truth consumers use only `start` and `end`: project those fields from
aligned, consistent rows before passing them to a strict truth parser. Review cut or
unaligned rows separately. Stdout includes only ordinal, scores and booleans; UTC
timestamps are confined to the external truth artifact. Input errors emit only
`{"error_count": 1}` and exit 1.

### Evidence extraction and separability

A manifest is an external JSON object with `stages`. Each stage contains `blocks`
(`path`, aware UTC `start`) and `truth` (`start`, `end`). Optionally provide
`known_graphics` as a flat PNG folder and `music_cues` as a list of reference audio paths.
An external `--truth` can instead supply a span array for a single stage, or
`{"stages":[{"truth":[...]}]}` matching manifest stage order. Display names are ignored.

```powershell
uv run --no-sync python ../scripts/validation/boundary_evidence_lab.py `
  --manifest D:\BoundaryLab\corpus.json --cache D:\BoundaryLab\cache `
  --audio-stats --picture --music-cue --whisper --voice-continuity `
  --out D:\BoundaryLab\evidence.json --markdown-out D:\BoundaryLab\evidence.md
```

All six families are opt-in. Missing tools, filters, optional runtimes or reference
audio produce a `skipped` family record; extraction/cache validation errors produce
`failed`. Read the statuses even when a report was successfully written. Features:

- `audio_stats`: one FFmpeg pass with aspectral flatness, centroid, flux, entropy and
  rolloff, ebur128 momentary loudness and astats RMS. Metadata frames are averaged per
  second. Digital-silence negative infinity is represented by the fixed -120 dB floor.
- `picture`: per-second maximum scene score, black intervals, and maximum normalized
  correlation against supplied 64x36 grayscale PNGs. Video graphics are sampled at
  1 fps; uniform images have zero similarity. The winning graphic is an ordinal only.
- `music_cue`: 8 kHz normalized correlation per second against each supplied reference,
  taking the best valid reference-start score, a detection at the fixed 0.8 threshold,
  and the winning reference ordinal. Decode and correlation use 60 s cores with overlap
  equal to the longest reference length, including matches across chunk seams. Incomplete
  reference placements are not scored.
- `whisper`: segment spans, no-speech probability, average log probability, compression
  ratio from the additive `WhisperEngine.inspect_window` accessor. It independently
  inspects at most 10 s using ED-0122's existing inference and alignment. Decoder-level probabilities are shared by the split segments of that
  window. The production adapter never calls this accessor and its outputs are unchanged.
  Non-speech tokens are suppressed by the existing decoder and are not measured.
- `voice_continuity`: adjacent pooled encoder cosine distances; only real audio frames
  contribute to pooling. A zero-norm vector gives no observation. Block joins are compared
  when the apparent gap or overlap is within `--join-tolerance` (default 2.0 s, also used
  by ground truth). Larger gaps/overlaps and stage changes reset continuity.
  Vectors are kept in memory and are never returned, cached, enrolled or clustered.

Feature caches are keyed by block-content digest, extractor version, binary/model identity
and relevant reference digests/settings. Cache reads are validated against closed numeric
schemas. Only sanitized feature rows and constrained referee answers are cached. Whisper
inference repeats when needed for private transcript/continuity; it never reloads an
embedding or transcript from disk. `runtime_seconds` is incremental elapsed work per block
and family, including cache lookup; `shared_extraction_seconds` discloses the Whisper work
reused by Whisper/continuity. Do not sum the shared field across families. Cold model startup
and provisioning are not an inference benchmark. Binary/model/reference digests are private
cache inputs except the explicitly reported referee checksum.

JSON and Markdown report each observed feature separately for starts and ends, per UTC
calendar stage-day and pooled. AUC compares seconds within inclusive +/-15 s of the role's
truth edges against seconds strictly more than 120 s from any truth edge. Ties get half
credit; absent positive/negative evidence gives null AUC. Duplicate seconds from overlapping
blocks are averaged before scoring. Each feature reports raw `auc`, `direction` (`higher`
or `lower`, whichever is more separable), and `separability = max(auc, 1 - auc)`. Tied
or absent AUC defaults to `higher`; absent AUC gives null separability. Peak search uses
+/-120 s, maxima for `higher` and troughs for `lower`, with earliest timestamp winning ties;
it reports inclusive 10/30 s hit rates and signed median lag. Uncovered
edges remain in hit-rate denominators. Sparse continuity is scored only at observed window
boundaries. Direction is selected descriptively using these truth labels. Stage-day rows
also report `held_out_direction`, chosen from pooled positive/negative observations of
the other stage-days, and `held_out_separability`, this day's AUC read in that direction
(AUC for `higher`, 1 - AUC for `lower`). It may be below 0.5. Tied training AUC chooses
`higher`; absent training AUC gives null held-out fields, and absent test AUC gives null
held-out separability. **Rank families by held-out separability**, not the descriptive
per-day maximum. Pooled rows choose direction using all days and label it with
`direction_scope: "all_stage_days"`; they are descriptive, not held-out estimates.
Stage-day descriptive directions have `direction_scope: "stage_day"`. No detector is
calibrated or trained, and these numbers do not qualify production accuracy.

### Optional language-model referee

Use an operator-provisioned **llama.cpp `llama-server` executable** at `--llm-binary`,
an external GGUF at `--llm-model`, its required `--llm-sha256`, and a required
`--llm-model-family` from the license-review allowlist: Qwen2.5 0.5B/1.5B/7B/14B/32B or
Phi-3.5-mini. The family argument is the operator's declaration of the provisioned model;
the actual bytes must match the checksum. Qwen2.5-3B, 72B, Llama and Gemma are not accepted
choices. The lab does not discover, obtain or license weights.

Add `--llm-referee` and those four options to the lab command. The lab starts a temporary
server child bound only to `127.0.0.1` on a locally selected port and closes it on exit.
There is no remote-server URL, proxy, Internet call or tool-enabled conversation. This
server option avoids Windows command-line limits: transcript data crosses only the local
in-memory HTTP request body, never argv or a prompt file. Runtime build/revision and model
SHA-256 are reported. The context is 32768 tokens; token-count preflight refuses oversized
windows and truncated responses are rejected. Pin and qualify the operator runtime before
interpreting a real run; tests use fake effects, not a downloaded llama.cpp executable.

Each truth edge and an equal number of negative slots is tested. Negative points come from
the strongest within-feature ranked raw candidates more than 120 s from any edge, separated
by more than 30 s. Insufficient candidates remain explicit skipped slots. Enable cheap
families alongside the referee to supply negatives. For edges and negatives alike, the
360 s window is centred on the evaluated point plus an offset drawn uniformly from
+/-120 s, deterministically seeded by point ordinal and fixed run seed 42. The edge's
position therefore varies within the window. Word times are relative to window start;
neither the evaluated point nor its offset is disclosed. The earlier truth-centred
window and candidate-at-zero wording leaked the anchor despite omitting explicit labels.

Sentences have numbered indices: gaps over 2 s split sentences; punctuation or 40 words
ends a sentence. The prompt asks only whether and where a talk start or end occurs in
the window. Transcript content is explicitly untrusted data. Truth still selects positive
windows for this targeted evaluation; these metrics are not an unbiased full-day scan.

Requests use GBNF-constrained JSON, temperature 0 and seed 42. Answers contain only bounded
indices or null and section labels `intro`, `talk`, `qa`, `mc_handoff`, `break`, `other`.
Strict validation rejects extra fields, duplicate keys, invalid indices and other labels.
Chosen starts map only to the first word's start; chosen ends to the last word's end.
Answers are cached by prompt/grammar/model/runtime/settings digest. Reports show median/p90
absolute error, matched-edge counts, negative agreement and missing-answer counts separately
for starts and ends, per stage-day and pooled. Referee runtime is attributed to the block
containing the candidate start placement; prerequisite transcript extraction is also recorded.

### Sanitization and synthetic validation

Never commit real media, manifests, names, transcripts, prompts or operator configuration.
Public reports contain ordinals, numeric measurements, booleans and closed labels only
(plus the required model checksum/runtime revision). Raw provider diagnostics are captured
and discarded; public errors never interpolate exception messages. Transcript words exist
only in process memory and in the temporary local referee request. No embeddings persist.

`backend/tests/test_boundary_evidence_lab.py` covers synthetic offsets, gaps, cuts including
short cuts hidden by an otherwise high score, low-score refusal, parsers, graphics, music,
continuity, day/overlap metrics, cache keys/poisoning, output collisions and sanitization,
missing tools, checksums, grammar, fake referee transport and word-time mapping.
`test_boundary_evidence_engine_accessor.py` verifies diagnostics, real-frame pooling,
suppression preservation and unchanged normal transcription outputs. NumPy-dependent tests
skip when the optional group is absent. Fixtures use pytest `tmp_path`, never a
repository-relative scratch directory. Additional review regressions cover seeded referee
windows, fractional recorder clocks, bounded local/global search counts, float32 FFT chunks,
quiet-tile acceptance fractions, lower-direction troughs, and music chunk seams. No test
needs media, models, a GPU or a network.
