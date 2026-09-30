# Live-chain validation and core transcription (ED-0119, ED-0120, ED-0121)

## Status

**Approved** (owner, 2026-09-30), with D1–D5 as recommended. ED-0119, ED-0120 and ED-0121 are allocated.

It follows:
- the owner's live-testing direction of 2026-09-30: simulate the live setting, where
  StageFlow sits at the tail of the signal flow, recordings appear in small blocks, and
  speed is primary. The first real-block replay is half a day at 1×, with transcription
  in the chain;
- the owner's acceptance of [ADR-0036](../adr/ADR-0036-core-transcription-gpl-free-engine.md)
  (core transcription with a GPL-free engine) and
  [ADR-0037](../adr/ADR-0037-owner-operated-gpu-appliance-baseline.md) (the appliance
  baseline).

## Execution authority

- **Classification:** Green once approved.
  - ED-0119 is validation tooling only.
  - ED-0120 implements ADR-0036's "on by default" for the existing asset-scoped transcript
    evidence (D1).
  - ED-0121 extends the ED-0115 replay tool.
- **Authority evidence:** ADR-0036, ADR-0037, ADR-0034 (Phase 7 live condition), ED-0115,
  and the owner direction above.
- **Implementation-ready:** yes. D1–D5 were approved on 2026-09-30.
- **ED numbers:** ED-0119 and ED-0120 were proposed to the owner on 2026-09-30. ED-0121
  is the next free number, split out because the replay upgrade is separable. All three
  are confirmed on approval.

## Problem statement

The current tests leave four gaps against the live setting:

1. **Transcripts are the core new evidence** (policy v5), but in live use there are none
   where suggestions are needed.
2. **The engine choice (ADR-0036) is unmeasured.** Its latency per block and its parity
   with today's transcripts are unknown.
3. **The replay leaves out parts of the live chain.** ED-0115 does not include
   transcription, copies files whole instead of growing them, and scores accuracy only
   at the end of the day.
4. **No end-to-end speed baseline exists** on real blocks at 1×.

## Verified current behavior

- **Transcription starts only for Session-associated media.** In
  `DemoApplication.reconcile_media` (`backend/app/demo/service.py`), timing and
  segmentation are enqueued for every registered asset when enabled. Transcription is
  enqueued only for media with a `session_id` and `AssociationStatus.ASSOCIATED`, and its
  idempotency key includes the Session.
  - The only manual trigger is `POST /sessions/process-transcription`, which requires a
    `session_id`.
- **Transcript evidence is already asset-scoped.** "Transcript Evidence Revision" is the
  accepted asset- and manifest-scoped evidence term
  ([transcription evidence readiness](../architecture/transcription-evidence-readiness.md)).
  A transcript is evidence about one immutable Completed Media Asset manifest revision,
  not a Session boundary or membership.
- **Suggestion runs use transcripts per asset.** They read an asset's transcript
  reference when one exists (`session_suggestions/service.py`). Without pre-association
  transcripts, live runs get no cues.
- **The engine:** the faster-whisper 1.2.1 adapter passes a media path, so PyAV decodes
  (`backend/app/infrastructure/transcription/faster_whisper.py`).
  - faster-whisper imports `av` at module load, and accepts in-memory audio arrays.
  - No StageFlow code imports PyAV directly.
- **The ED-0115 replay:**
  - copies blocks with an atomic `.partial` rename;
  - drives timing and segmentation `--once` workers, then suggestion runs;
  - reports time-to-first-suggestion, stability and final accuracy;
  - has no transcription step, no growing-file mode, and no accuracy at the time of use.
- **Local resources:**
  - the corpus: three W3S25 Studio 1 days of 10-minute recorder blocks, local only;
  - the LGPL FFmpeg binary at an explicit path;
  - a CUDA GPU on the development machine, which is ADR-0037's provisional profile.

## Decisions (owner approval of this plan approves the recommended defaults)

- **D1. Transcribe every registered asset on arrival (ED-0120).**
  - When transcription is enabled for an Event (ADR-0036: on by default),
    `reconcile_media` enqueues a transcription operation for **every registered Completed
    Media Asset of the Event**, in arrival order. Session association no longer matters.
  - Idempotency is by asset, manifest revision and execution profile, so an asset is
    transcribed once regardless of later association.
  - The existing Session-scoped trigger still works. It reuses the same operation when
    the asset has already been transcribed or enqueued.
  - Session, association and Editorial semantics are unchanged; transcripts stay
    asset-scoped evidence.
  - **Consequence:** more GPU work (every block, not only associated ones). ADR-0037
    budgets it, and ED-0121 and Run 002 measure it.
  - **Alternative:** keep Session-scoped transcription. Rejected, because v5's cue
    evidence would never exist for new suggestions.
- **D2. The engine spike (ED-0119) is measurement-only.** A validation script in
  `scripts/validation/` compares, on owner-supplied local blocks:
  - **Baseline:** the current adapter, with PyAV decoding the path.
  - **Option A:** the LGPL FFmpeg binary decodes to 16 kHz mono PCM, fed as an array to
    the same Whisper model and settings.
  - **Option B (optional):** a whisper.cpp binary at an explicit path, when the operator
    supplies one.
  - **Reported, sanitized:**
    - seconds per block per engine, on GPU and on CPU;
    - word-level agreement: text-aligned word timestamp deltas, median and p95;
    - cue-hit agreement on the composed Conference stage lists (count and timing);
    - the same timings while a concurrent NVENC render runs, using the explicit-path
      FFmpeg.
  - No production code changes, no dependency, and no media, text or paths in the output.
  - Building the production GPL-free adapter (removing PyAV) is a later directive,
    chosen from the spike's result.
- **D3. Replay upgrades (ED-0121):**
  - **Transcription in the chain:** after segmentation, wait for, or run with
    `--once`, the transcription work for the new asset. Cue lists are composed for the
    review Event through the existing boundary-cue API, with the Conference profile.
  - **Arrival mode `growing`:** the tool writes each block to its final name in chunks,
    evenly over the block's duration divided by the pace, the way a recorder writes. This
    exercises discovery's readiness and stabilization path. The default stays `atomic`.
  - **Accuracy at the time of use:** for each talk, start and end error at its first
    matching suggestion, at +5 min and at +15 min of media time, plus the existing final
    accuracy.
  - **Per-stage timings:** per block, media seconds from the block closing to
    registration, timing done, segmentation done, transcription done, and the next
    suggestion run, with medians and p95 values.
  - **An evidence availability timeline:** for each block, when its segmentation and
    transcript became available (ordinals and seconds only). The owner can then evaluate
    v5 offline in the harness, at each run time, on only the evidence available then
    (D5).
  - **`--profile-label`:** a closed-charset label naming the appliance profile
    (ADR-0037).
- **D4. Live Replay Run 002 protocol:**
  - A **half day at 1×**: one real W3S25 Studio 1 day's morning, from recording start to
    the lunch break, local only.
  - Transcription is on (D1). Arrival mode is `growing`. A suggestion run follows every
    block.
  - The live policy is v3, because the service default only changes in ED-0118.
  - **Recommended day:** day 3's morning, the hardest real-schedule case for v3.
  - The report records the provisional profile. Its result doc,
    `session-suggestions-replay-002.md`, is sanitized.
- **D5. The ED-0118 live condition, made concrete.**
  - Using Run 002's evidence availability timeline, the owner evaluates v5 (Option B
    constants) offline at each run's time point.
  - v5's advantage counts as arriving early enough when, for each talk, v5's accuracy at
    +5 min is at least v3's accuracy at +5 min.
  - A talk where transcription arrives too late for v5 to beat v3 by +15 min counts
    against it.
  - Failure blocks ED-0118 pending an owner decision; engine speed (ED-0119) is the
    lever.

## In scope

- **ED-0119:** `scripts/validation/transcription_engine_spike.py`, its README section,
  and fake-effect tests.
- **ED-0120:** Event-wide transcription enqueue in `reconcile_media`, the asset-scoped
  idempotency key, reuse by the Session-scoped trigger, tests (memory and PostgreSQL),
  and docs.
- **ED-0121:** replay tool options and report fields, a README update, and fake-effect
  tests.

## Out of scope

- The production GPL-free adapter (a later directive after ED-0119).
- The ED-0075 guard change and SBOM regeneration (with that adapter).
- Priority scheduling of GPU work between transcription and render (a later plan, per
  ADR-0037).
- Policy changes.
- The ED-0118 freeze.
- UI changes.
- Any real media or transcript in the repository.

## Constraints

- No dependency.
- The ED-0075 exclusion stays in force until the GPL-free adapter lands. Local
  transcription for the spike and the replay uses the operator-installed group on this
  machine, which is not distribution.
- Offline: no network use.
- Sanitized outputs.
- Held-out synthetic seeds stay unused.
- No Session or association semantics change.
- Migrations: none expected for ED-0120. The idempotency key lives in the existing
  operation input. If a schema change turns out to be needed, stop and report.

## Test strategy

- **ED-0119 and ED-0121:** fake-effect unit tests (no media, GPU or network) for option
  parsing, pacing and chunked writing, metric computation, sanitization and exit codes.
- **ED-0120:**
  - every registered asset is enqueued once;
  - the Session trigger reuses the asset's operation;
  - a disabled Event enqueues none;
  - restart and replay idempotency;
  - PostgreSQL round trip, rolled back;
  - existing Session-scoped tests unchanged.
- The full host backend suite, Ruff, Pyright and `git diff --check`.
- **Owner runs:** the ED-0119 spike on about 6 real blocks, recorded as a result; then
  Live Replay Run 002 (D4) and the D5 evaluation.

## Acceptance criteria

- [ ] ED-0119 merged; spike result recorded, with engine timings and parity, and a
  recommendation between A and B for the GPL-free adapter.
- [ ] ED-0120 merged. Registered assets are transcribed without a Session, and existing
  behavior is unchanged.
- [ ] ED-0121 merged, with the growing-file mode, time-of-use accuracy, per-stage
  timings and the availability timeline.
- [ ] Live Replay Run 002 recorded (D4), with the D5 evaluation and the ED-0118 go or
  no-go.

## Rollback

- ED-0119 and ED-0121 are validation tools; revert the code.
- ED-0120: revert the code. Already-enqueued or completed asset transcripts remain valid,
  immutable evidence.
