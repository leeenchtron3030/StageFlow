# GPL-free transcription engine (ADR-0036 option A)

## Status

**Approved** (owner, 2026-09-30), with D1–D7 as recommended, including the D5 parity
tolerances and the D6 profile-switch rule. **ED-0122** is allocated for the additive
engine. **ED-0123** is reserved for the default switch, and its scope is confirmed when
the owner parity run passes.

## Execution authority

- **Classification:** Green once approved.
  - ADR-0036 (Accepted 2026-09-30) authorizes the engine, its decode boundary, and
    replacing the `transcription` dependency group.
  - The ED-0119 result chose option A over B.
  - The decisions below are implementation choices inside that authority. D5 (parity
    tolerances) and D6 (when a profile switch applies) are owner judgments, which is why
    the plan needs approval.
- **Authority evidence:**
  - [ADR-0036](../adr/ADR-0036-core-transcription-gpl-free-engine.md), decisions 2–4;
  - [ADR-0037](../adr/ADR-0037-owner-operated-gpu-appliance-baseline.md);
  - [Transcription Engine Spike - Run 001](../validation/results/transcription-engine-spike-001.md),
    whose recommendation and requirements this plan carries over;
  - the ED-0075 [distribution boundary](transcription-distribution-boundary.md);
  - the [SBOM record](../security/dependency-license-sbom-2026-08-21.md).
- **Implementation-ready:** yes. D1–D7 were approved on 2026-09-30.
- **Escalation:** stop and report if any of the following turns out to be needed:
  - a change to the transcript evidence contract, its storage schema or the Work
    Execution port;
  - a dependency outside the licenses in D2;
  - a native library bundled in a candidate wheel whose license is not permissive.

## Related findings or ADRs

- **ADR:** ADR-0036, ADR-0037, ADR-0029 (GPU worker), ADR-0027 and ADR-0033 (the
  explicit-path LGPL FFmpeg pattern).
- **Engineering Directives:** ED-0075 (the boundary this replaces), ED-0119 (the spike),
  ED-0120 (Event-wide transcription, whose operation identity includes the execution
  profile).

## Problem statement

Transcription is on by default under ADR-0036, but the only engine is faster-whisper.
Its package imports PyAV at import time, and the PyAV wheel bundles a GPL-configured
FFmpeg. Under ED-0075 the transcription group stays operator-installed and excluded from
anything distributed. Transcription therefore cannot become a core, default dependency
until an engine exists that never loads PyAV.

The ED-0119 spike showed that the replacement path (LGPL FFmpeg decode to PCM, with the
same CTranslate2 Whisper model) matches today's speed. It also showed that parity holds
only when the stereo downmix is averaged.

## Verified current behavior

- **Adapter** (`backend/app/infrastructure/transcription/faster_whisper.py`):
  - `FasterWhisperExecutionAdapter` loads `faster_whisper.WhisperModel` lazily, through
    `_default_model_factory`.
  - It passes the resolved media **path** to `transcribe(...)`, with beam 5, word
    timestamps, `vad_filter=False` and `condition_on_previous_text=True`, and the
    requested language.
  - It requires `device == "cuda"` and `compute_type == "float16"`. It pins
    faster-whisper 1.2.1 and CTranslate2 4.8.1.
  - Its provenance is `provider_id="faster-whisper"`, `execution_tool_id="ctranslate2"`
    and `execution_revision="stageflow-faster-whisper-adapter-1.0"`.
- **The package itself pulls in PyAV.** faster-whisper 1.2.1's `transcribe.py` imports
  `faster_whisper.audio` (PyAV), `utils` (`huggingface_hub`, `tqdm`) and `vad`
  (onnxruntime) at module level. Importing anything from the package loads PyAV.
  - The pieces StageFlow actually uses are `transcribe.py` (1,941 lines; only the
    beam/word-timestamp path is needed), `feature_extractor.py` (230; numpy),
    `tokenizer.py` (320; `tokenizers`) and part of `utils.py`.
  - faster-whisper is MIT licensed.
- **Locked versions** (`backend/uv.lock`): ctranslate2 4.8.1, tokenizers 0.23.1, numpy
  2.5.2, av 18.1.0, faster-whisper 1.2.1, huggingface-hub 1.28.0, onnxruntime 1.29.0.
- **The `transcription` dependency group** is `ctranslate2==4.8.1` and
  `faster-whisper==1.2.1` (`backend/pyproject.toml`).
  `backend/tests/test_transcription_distribution_boundary.py` guards that it is not a
  default group, and that the excluded names are not default dependencies.
- **Configuration** (`app/core/config/deployment.py`, `LocalTranscriptionConfiguration`):
  `provider` (default `faster-whisper`), `model_path`, `device` (`cuda`),
  `compute_type` (`float16`), `execution_profile_id` and `execution_profile_version`.
- **The profile is part of operation identity.**
  - Transcription targets and operations are keyed by the execution profile id and
    version (`app/demo/service.py`, about lines 150–206).
  - Workers claim only operations whose profile matches their capability
    (`app/infrastructure/postgres/transcription_work_repository.py`, about lines
    605–615).
  - So under ED-0120, a new profile id enqueues a new operation for every registered
    asset of the Event.
- **The spike result** (development machine; not the appliance):
  - Option A's speed equals the baseline's on GPU: about 16 s per 10-minute block, and
    about 25 s under an NVENC render.
  - The FFmpeg `-ac 1` stereo downmix is exactly +3 dB louder than PyAV's. With
    channel averaging, the PCM matches PyAV to 16-bit rounding, and parity follows.
  - A CPU run needs a CPU-valid compute type: `float16` fails on CPU, and `int8` works.

## Desired behavior

A StageFlow-owned transcription adapter produces transcript evidence equivalent to
today's without loading PyAV, `faster_whisper` or any GPL component:
- the operator's LGPL FFmpeg binary decodes the audio;
- CTranslate2 runs the same Whisper model.

Once it is qualified on the appliance, it becomes the default engine and its
dependencies become default dependencies. faster-whisper and ED-0075's exclusion are
then retired, and the SBOM shows no GPL or AGPL component.

## Decisions (approved by the owner 2026-09-30)

- **D1. The engine is a StageFlow-owned port of the subset in use.**
  - **Location:** a new module, `app/infrastructure/transcription/ctranslate2_whisper/`.
  - **What it ports** from faster-whisper 1.2.1, with the MIT license notice retained
    in the module:
    - log-mel feature extraction;
    - the tokenizer wrapper;
    - the sequential 30-second window loop, with temperature fallback, the
      compression-ratio, log-probability and no-speech thresholds, and
      previous-text conditioning;
    - word-timestamp alignment through `ctranslate2.models.Whisper.align`.
  - It ports only the settings StageFlow uses (beam 5, word timestamps, no VAD, a fixed
    language) and the same defaults, so its output is comparable with today's.
  - It never imports `faster_whisper`, `av`, `huggingface_hub`, `onnxruntime` or `tqdm`.
    There is no batched pipeline, VAD or model download.
- **D2. Dependencies:** a new group, `transcription-core`, with `ctranslate2==4.8.1`
  (MIT), `tokenizers==0.23.1` (Apache-2.0) and `numpy` at the locked version (BSD-3).
  - **Before adding it:** inventory the native libraries bundled in the CTranslate2
    wheel for Windows and Linux, for example the OpenMP runtime. Record their licenses
    in the plan's completion record. Any non-permissive license is an escalation.
  - **CUDA runtime:** stays operator-provisioned, as today.
  - **While ED-0122 is active:** the old `transcription` group stays for comparison, and
    `transcription-core` is not yet a default group.
- **D3. Decode:** the operator's LGPL FFmpeg runs as a separate process at an explicit
  path.
  - **Configuration:** a new optional `ffmpeg_path` in `[local_transcription]`. It is
    required when `provider` is the new engine, and absent fields stay compatible.
  - **Command:**
    - `-map 0:a:0`;
    - an explicit **equal-weight channel average** built from the probed channel count
      (for stereo, `pan=mono|c0=0.5*c0+0.5*c1`), never a bare `-ac 1`;
    - `-ar 16000 -f s16le`;
    - conversion to float32 by `/ 32768.0`, the way PyAV's path does.
  - **Bounds:** a decode timeout, and a cap on output size based on the probed
    duration.
- **D4. Provider identity and profiles.**
  - **Identity:** `provider_id = "stageflow-ctranslate2-whisper"`,
    `execution_tool_id = "ctranslate2"` and its own `execution_revision`, so its
    transcripts are distinguishable from faster-whisper's.
  - **Allowed (device, compute type) pairs:** (`cuda`, `float16`) and (`cpu`, `int8`).
    Any other pair is refused at construction, never at the first inference.
  - **Example profile ids:** `ct2-whisper-large-v3-turbo-cuda-float16` and
    `ct2-whisper-large-v3-turbo-cpu-int8`.
  - **Model:** the same offline-provisioned model directory. `tokenizer.json` is
    required, and the adapter never downloads.
- **D5. Parity tolerances for the switch**, measured per block against the
  faster-whisper adapter on the same blocks and machine, with the ED-0119 metrics:
  - words matched ≥ 95% on every block;
  - p95 word start difference ≤ 0.6 s on every block;
  - cue hits, over the whole set: the new engine's total is at least 90% of the
    baseline's, and at least 90% of its hits match a baseline hit.

  These are the ED-0119 values. Since D3 makes the decode equivalent, near-identical
  output is expected, and larger gaps point to a porting defect.
- **D6. When a profile switch applies.**
  - **Switch between Events.** A new Event gets the new profile. An existing Event
    keeps its profile for its whole life.
  - **A mid-Event switch is possible but deliberate.** ED-0120 would re-transcribe every
    registered asset under the new profile. Earlier transcripts remain valid,
    immutable evidence.
  - Document this in the operator README.
- **D7. Sequencing:**
  - **ED-0122:** the engine, decode, configuration, tests, and a parity mode in the spike
    script (`--candidate stageflow`) that compares the faster-whisper adapter with the
    new adapter end to end. The default provider is unchanged.
  - **Owner parity run:** on the appliance-class GPU when available, otherwise on the
    development machine as a provisional profile. Six or more real blocks, with and
    without render load, plus CPU. Recorded as a validation result against D5.
  - **ED-0123 (proposed), after a passing run:**
    - switch the default provider and profile;
    - make `transcription-core` default dependencies;
    - remove the faster-whisper adapter and the `transcription` group;
    - replace the ED-0075 guard with a GPL-free guard (no `av`, `faster-whisper`,
      `onnxruntime` or `huggingface-hub` in the default resolution);
    - regenerate the SBOM;
    - update the ED-0075 and ADR-0036 status records.

## In scope (ED-0122)

- The `ctranslate2_whisper` engine module and `CTranslate2WhisperExecutionAdapter`. It
  implements the same execution contract as `FasterWhisperExecutionAdapter`: the same
  normalized result, the same partial and failure codes, and lease renewal per segment.
- The FFmpeg decode helper, with the channel-average downmix and its bounds.
- `LocalTranscriptionConfiguration` gains an optional `ffmpeg_path` and accepts the new
  provider id and the D4 pairs. The demo worker selects the adapter from `provider`.
- The `transcription-core` dependency group and the lockfile update.
- The parity mode in `scripts/validation/transcription_engine_spike.py`, with its tests.
- Docs: the transcription evidence readiness architecture doc (engine and profile
  semantics), the backend README and the demo README (configuration and the D6
  guidance), and the validation README.

## Out of scope

- Switching the default, removing faster-whisper, ED-0075 supersession and SBOM
  regeneration (ED-0123).
- whisper.cpp (option B).
- VAD, batching, diarization, translation, and languages other than English.
- GPU scheduling between transcription and rendering (a later plan, per ADR-0037).
- Any transcript evidence schema or contract change, policy change or UI change.

## Constraints

- **Architecture:**
  - adapter code stays in infrastructure, behind the existing transcription execution
    port;
  - the domain never imports CTranslate2 or numpy;
  - modular monolith; no new service.
- **Compatibility:**
  - existing configurations, the faster-whisper adapter and existing transcripts keep
    working unchanged;
  - new fields are optional;
  - provider identity distinguishes the engines.
- **Offline:** no network at any time. The model and binaries are provisioned locally,
  and nothing downloads models.
- **Licensing:**
  - no GPL or AGPL component may be imported, loaded or added;
  - `av` must not be importable from the new adapter's code path;
  - a test proves this in a clean interpreter (`sys.modules`).
- **Data:** no real media or transcripts in tests. Synthetic PCM fixtures only.

## Implementation approach

1. **Dependency inventory and group.** List the native libraries in the CTranslate2
   wheels for Windows and Linux and record their licenses. Add `transcription-core` and
   update the lockfile.
2. **Decode helper.**
   - Probe the channel count with the configured ffprobe (or ffmpeg).
   - Build the average expression for 1–8 channels, and refuse anything outside that
     range.
   - Run FFmpeg with a timeout and an output cap, and convert s16 to float32.
3. **Engine port.** Features, tokenizer, window loop and alignment, typed for Pyright.
   Model loading is injected, so tests use a fake CTranslate2 model.
4. **Adapter.**
   - Validation at construction: provider, pair, model directory, `tokenizer.json`, the
     FFmpeg path and the versions.
   - Execute: resolve the path, decode, transcribe and normalize, mirroring the existing
     adapter's error mapping.
5. **Configuration and worker selection**, with tests.
6. **Spike parity mode** and its documentation.

Each step can be reviewed on its own, and the default provider never changes in
ED-0122, so a revert restores today's behavior.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/infrastructure/transcription/ctranslate2_whisper/` | New: features, tokenizer, window loop, alignment, decode, adapter |
| `backend/app/infrastructure/transcription/__init__.py` | Export the new adapter |
| `backend/app/core/config/deployment.py` | Optional `ffmpeg_path`; new provider id and allowed pairs |
| `backend/app/demo/worker.py` | Select the adapter by `provider` |
| `backend/pyproject.toml`, `backend/uv.lock` | `transcription-core` group |
| `scripts/validation/transcription_engine_spike.py` | `--candidate stageflow` parity mode |
| `backend/tests/test_ctranslate2_whisper_*.py` | New unit and contract tests |
| `docs/architecture/transcription-evidence-readiness.md`, READMEs | Engine, profile and D6 guidance |

## Data or migration considerations

None verified as needed:
- Provider identity and the execution profile are already recorded per transcript and
  operation.
- Under ED-0120, a profile switch creates new operations (D6). Old transcripts remain
  immutable evidence.
- No schema change and no migration. Stop if one appears to be needed.

## Failure and recovery considerations

- The existing codes keep their retry semantics:
  - **Not retryable:** a missing CUDA runtime, model, FFmpeg binary or tokenizer
    (`provider_runtime_unavailable`, `cuda_runtime_unavailable`,
    `provider_model_unavailable`).
  - **Retryable:** a decode failure or timeout (a new code, `media_decode_failed`), and
    `provider_execution_failed`.
- A failure while iterating segments, after some segments exist, yields a `PARTIAL`
  result, as today.
- Leases are renewed during decode and per window.

## Observability requirements

- Provenance names the engine, its version, CTranslate2's version, the device and
  compute type through the profile, and the decode tool's identity.
- The worker's capability reports the profile. Failure codes are closed.
- No paths or transcript text appear in diagnostics.

## Test strategy

- **Unit tests** (no GPU or media):
  - feature extraction against fixed numeric fixtures, generated once from the reference
    implementation and committed as small synthetic arrays;
  - the window loop's fallback and thresholds, with a fake model;
  - the alignment-to-words mapping;
  - tokenizer special tokens;
  - the downmix expression for 1–8 channels;
  - the s16 conversion;
  - decode bounds and timeouts;
  - pair refusal at construction.
- **Contract tests:** the adapter's normalized result, and its partial and failure
  mapping, are identical in shape to the faster-whisper adapter's tests.
- **The licensing guard:** in a clean subprocess, importing and running the adapter
  path loads none of `av`, `faster_whisper`, `huggingface_hub`, `onnxruntime` or
  `tqdm`.
- **Host-only checks** (skipped when the transcription runtimes are absent):
  - PCM equivalence on a generated synthetic stereo tone with unequal channels: PyAV
    through the old group against the FFmpeg channel average, within one 16-bit step;
  - a short end-to-end CPU `int8` run on synthetic audio.
- **Commands:** the full host backend suite, Ruff, Pyright and `git diff --check`.
- **Owner run:** the parity run in D7, recorded as a validation result.

## Acceptance criteria

- [ ] ED-0122 merged: the engine, decode, configuration, worker selection, parity mode,
  docs and tests, with the default provider unchanged.
- [ ] The CTranslate2 wheel's native-library license inventory is recorded, with no
  non-permissive component.
- [ ] The licensing guard test proves that no PyAV, faster-whisper, huggingface_hub,
  onnxruntime or tqdm is loaded.
- [ ] Owner parity run recorded: D5 tolerances met on GPU (with and without render load),
  and a CPU `int8` run completed.
- [ ] ED-0123 proposed with the switch, guard replacement and SBOM regeneration.

## Rollback or reversal

- ED-0122 is additive. Reverting the code and the dependency group restores today's
  behavior.
- Transcripts produced by the new engine remain valid, immutable evidence under their
  own provider identity.
- No step is irreversible.

## Open questions

- Is the appliance-class GPU available for the parity run, or is the run recorded as
  provisional on the development machine (as ED-0119 was)?
- Should multi-channel camera sources (for example 4 × PCM) average all channels (D3), or
  pick a channel by a source setting? The default averages, matching PyAV. A per-source
  channel choice would be a separate decision.

## Completion record

- Implemented revision:
- Files and migrations actually changed:
- Commands and tests actually run:
- Results and warnings:
- Execution authority used:
- Approved deviations:
- Rollback status:
- Remaining work:
