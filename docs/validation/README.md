# StageFlow validation artifacts

## Purpose

This directory holds non-media validation contracts and sanitized results. It does not
hold event footage, credentials, database dumps, private absolute paths, sensitive raw
transcripts, or provider payloads.

Validation evidence describes what a specific run established. It does not silently
promote a proposed capability to current implementation or establish production/Event
readiness.

## Index

| Artifact | Purpose | Status |
| --- | --- | --- |
| [Demo 1 qualified fallback baseline](results/demo1-qualified-baseline-2026-08-20.md) | Frozen StageFlow/runtime/topology/Devcon/Program/manual-workflow record for Demo 2 fallback | **QUALIFIED FALLBACK** at `504b32567cf856082642697b6974859290c65020` |
| [Real transcription engine evaluation](transcription-engine-evaluation.md) | Provider-neutral Windows/RTX matrix, metrics, PostgreSQL worker evidence, and scoped acceptance record | Accepted for Demo 1 and the first real local implementation; broader selection awaits representative event qualification |
| [Real-Event Playback Validation and UX Calibration](../plans/real-event-playback-validation.md) | Current-Kernel direct/vMix replay runbook, measurements, UX calibration, and future reuse | Run 002 passed; Run 003 invalid; Run 004 partially qualified turnover |
| [Run 004 qualification-tooling hardening](../plans/run-004-qualification-tooling-hardening.md) | Turnover authority guard, host-local lock, atomic evidence, incremental checkpoints, and runtime protection | Green qualification-only hardening validated and used by Run 004 |
| [Run 004 qualification closure and timing telemetry](../plans/run-004-qualification-closure.md) | Immediate authority timestamp capture, source-aware runtime telemetry, and partial qualification closure | Green qualification-only closure completed and validated |
| [vMix media timing evidence reconnaissance](vmix-media-timing-reconnaissance.md) | Sanitized read-only Run 004 container, stream, packet, and candidate-interval findings | Green reconnaissance complete; production authority not qualified |
| [vMix media timing calibration experiment](vmix-media-timing-calibration.md) | Controlled experiment for measuring recorder timing against independent content markers | Harness self-check complete; controlled vMix execution not run |
| [Recorder calibration harness](recorder-calibration-harness.md) | Deterministic marked-source generation, decoded content-boundary analysis, and controlled vMix runbook | Tooling implemented/self-checked; vMix qualification not run |
| [Demo 2 Autonomous Event Node initial automated validation](results/demo2-autonomous-event-node-initial-automated-2026-08-20.md) | Coordinator, automatic media/Program, worker status, package approval, UX, launcher, privacy, and full-gate evidence | **PARTIAL — Yellow association decision and hardware rehearsal pending; Demo 1 remains fallback** |
| [Demo 2 branch rehearsal - 2026-08-24](results/demo2-branch-rehearsal-2026-08-24.md) | Branch-only record of an earlier, unqualified ED-0071 attempt (before ED-0071 Run 001): local rebase and guarded two-machine rehearsal | **UNQUALIFIED - stopped before startup because preserved Demo database lacks current-main migration 0010; Demo 2 not promotion-qualified** |
| [Demo 2 branch rehearsal - 2026-08-25 A](results/demo2-branch-rehearsal-2026-08-25-a.md) | Branch-only record before ED-0071 Run 001; branch-local ED-0072 (superseded numbering; see ED-0081) database upgrade and first write-bearing two-machine rehearsal | **CORE WRITE-BEARING FLOW QUALIFIED; PR promotion unqualified because ED-0063 live degraded-loop gate remains unproven** |
| [Demo 2 branch rehearsal - 2026-08-25 B](results/demo2-branch-rehearsal-2026-08-25-b.md) | Branch-only record before ED-0071 Run 001; Supplemental isolated-source repeatability rehearsal and newly authorized guarded PUT | **SECOND CLEAN WRITE-BEARING FLOW QUALIFIED; PR promotion remains unqualified and fail-closed limitations are preserved** |
| [Recorder calibration harness self-check](results/recorder-calibration-harness-self-check.md) | Sanitized FFmpeg source/60s/30s/partial fixture evidence and limitations | Qualification-tool readiness PASS; recorder qualification NOT RUN |
| [Media timing qualification probe](../../backend/tests/qualification/media_timing_probe.py) | Bounded local inspection with sanitized raw observations and explicitly unqualified derivations | Implemented qualification tooling; prohibited from authority use |
| [Bounded real-event playback runner](../../backend/tests/qualification/real_event_playback.py) | Explicit validation-only commands, bounded cycle cadence, retained identities, atomic local results, and reconstruction | Implemented qualification tooling; not a watcher or public API |
| [Safe local validation controller](../../scripts/validation/README.md) | PowerShell wrapper, Run-isolation safeguards, action map, and guarded Run 004 same-Stage procedure | Hardened qualification tooling; Run 004 not started |
| [Reference-corpus manifest example](reference-corpus-manifest.example.yaml) | Human-readable, diffable corpus and ground-truth annotation shape | Example only; not a runtime schema |
| [Playback-run result template](real-event-playback-run-result-template.md) | Sanitized evidence record for one direct or vMix run | Reusable template |
| [Run 002 — real-media Durable Event-Mode Kernel baseline](results/real-event-playback-run-002.md) | Sanitized real-media, Session/package, reconstruction, finding, performance, and UX evidence | **PASS — Real-media Durable Event-Mode Kernel baseline** |
| [Run 003 — invalid same-Stage turnover execution](results/real-event-playback-run-003.md) | Sanitized missing-Session authority, conservative media preservation, and qualification-tooling incident evidence | **INVALID — intended same-Stage turnover qualification not executed**; secondary conservatism diagnostic pass |
| [Run 004 — same-Stage turnover partial qualification](results/real-event-playback-run-004.md) | Sanitized lifecycle, media, association-policy, authority-latency, and runtime-estimator evidence | Lifecycle/preservation/policy **PASS**; content-correct automatic association **INCONCLUSIVE / NOT QUALIFIED** |
| [Demo 2 hardware rehearsal — Run 001](results/demo2-hardware-rehearsal-001.md) | Sanitized two-machine autonomous media/transcription/approval evidence and unexercised failure-path criteria | **PARTIAL QUALIFICATION** — 7 of 10 criteria pass; worker projection, ED-0063 safety net, and restart reconstruction **NOT QUALIFIED**; Demo 2 not promotion-qualified |
| [Demo 2 hardware rehearsal — Run 002](results/demo2-hardware-rehearsal-002.md) | Sanitized single-host offline evidence for ED-0071 criteria 4, 6, 7 on the provider-neutral source: worker projection, live ED-0063 catch-all degraded/recovery, and restart reconstruction | **QUALIFIED** — criteria 4, 6, 7 pass; with Run 001 all ten ED-0071 criteria have passing evidence; Demo 2 promotion-qualified; PostgreSQL-outage leg not exercised live; not Event certification |
| [NVENC render benchmark - Run 001](results/render-benchmark-001.md) | Sanitized real-block NVENC/libx264 speed, size, SSIM/PSNR, and CUDA-transcription overlap evidence | **MEASURED** - NVENC 1.415x faster than libx264 in the bounded harness; neither arm met the anticipated sub-minute duration; narrow overlap showed no material contention |
| [Native FFmpeg render benchmark - Run 002](results/render-benchmark-002.md) | Sanitized native FFmpeg CPU-/CUDA-decode NVENC throughput (3 repetitions each), same-run PyAV baseline, SSIM/PSNR, and CUDA-transcription overlap evidence on the Run 001 corpus | **MEASURED** - native CUDA decode 48.91 s for 657.39 s of source (13.4x real time), 8.49x faster than the same-run PyAV path; first-order sizing input only, not a throughput guarantee |
| [Multi-encode render benchmark - Run 003](results/render-benchmark-003.md) | Sanitized per-GPU scaling evidence for 1-4 simultaneous native CUDA-decode→NVENC encodes: aggregate/per-encode timing, efficiency, session refusal, output identity, and GPU engine telemetry | **MEASURED** - aggregate throughput flat at ~13.6× real time for N = 1..4 (NVENC saturated by one encode); no refusal to N = 4; all outputs byte-identical; first-order sizing input only |
| [Render Durable Operation - Run 001](results/render-durable-operation-001.md) | Owner real-GPU validation of ED-0087: an approved Session Assembly revision rendered by the render worker, with identity, manifest, decode, and frame-count checks | **PASSED** - output SHA-256/size and manifest match the registered row; full decode OK; frame count exact; follow-ups: mixed-frame-rate duplicate timestamps, and discovery supplies no media start times |
| [Render Durable Operation - Run 002 (profile v2)](results/render-durable-operation-002.md) | Owner real-GPU validation of ED-0089: v2 constant-rate re-render of the Run 001 revision, with identity, timestamp, decode, duration, and throughput checks | **PASSED WITH ONE CRITERION NOT MET AS WRITTEN** - 0 duplicate PTS (Run 001: 22), 0 decode warnings, identity matches; duration within ~2 frames of v1 but 0.334 s short of the naive per-file sum (concat joins on timestamps) |
| [Render Durable Operation - Run 003 (profile v3, audio)](results/render-durable-operation-003.md) | Owner real-GPU validation of ED-0098: v3 audio renders of the Run 002 media and of synthetic flash/beep clips (silent, 44.1 kHz mono, and 25 fps inputs), with identity, stream, sync, silence, constant-rate, decode, determinism, and throughput checks | **PASSED AFTER A DEFECT FIX** - merged code let each input's audio overrun its video by minutes (`apad` + `-shortest`), leaving 200–270 s gaps at joins; after the exact sample-count fix: A/V duration difference 0.0 ms, 0 irregular frame steps, max marker offset 18.1 ms (no added drift), silent bumper −inf dB, byte-identical re-renders of both revisions; attempt 88.1 s vs 52.4 s for v2 |
| [Render Durable Operation - Run 004 (render quality per Event)](results/render-durable-operation-004.md) | Owner real-GPU validation of ED-0099: every preset at its defaults plus the High upper and Compact lower adjustment bounds, on real and synthetic sync media, with frozen-setting, resolution, bitrate, stream, sync, silence, constant-rate, decode, and throughput checks | **PASSED WITH ONE CRITERION NOT MET AS WRITTEN** - video within 5% of target at every setting, audio within 4 kbit/s except 320 kbit/s → 261 kbit/s (native AAC undershoot); A/V difference 0.0 ms, 0 irregular steps, sync markers unchanged (max 18.1 ms), silent bumper −inf dB; 76.3–98.2 s for 662.5 s of media |
| [Media Segmentation Evidence - Run 001](results/media-segmentation-001.md) | Owner real-FFmpeg validation of ED-0103: synthetic spans, end-of-file silence and freeze, audio-only and video-only inputs, and real recorder blocks against a manual command-line reference | **PASSED** - synthetic spans exact (AAC delay ≤16 ms), end-of-file intervals closed without error, real block identical to the reference; observation: changeovers can carry audio, so freeze is the primary signal |
| [Session Suggestions - early accuracy check 001 (policy v1)](results/session-suggestions-accuracy-001.md) | Owner-requested early check of policy v1 against decoded ground truth for 28 main-stage talks (three days, 112 recorder blocks, production segmentation adapter), with simulated schedule drift and threshold/selection experiments | **TARGET MET ONLY WITH AN EXACT SCHEDULE** - 27–28/28 suggested; median start/end error 15/24 s at 0 drift but 47/66 s at ±5 min and minutes beyond; in-talk freezes (median 56 s, silent share 0.00) outnumber real changeovers (median 284 s, 0.18) |
| [Session Suggestions - Accuracy Run 002 (policy v1 vs v2)](results/session-suggestions-accuracy-002.md) | Owner acceptance step for ED-0105: merged v1 and v2 policies, with and without transcript cues, against the same 28-talk ground truth, using the ED-0105 evaluator (IoU ≥ 0.5), five drift seeds, independent and whole-day drift, and a prototype comparison | **ACCEPTANCE NOT MET BEYOND ±5 MIN OF DRIFT** - v2 recall 0.93 and 14/18 s at 0 drift; ±5 min within 60 s only with cues; ±10/±15 min recall 0.68–0.86 with medians up to minutes; the ±20 min candidate cap and absolute plan distance explain most of the gap to the prototype; owner decision on options A/B/C |
| [Session Suggestions - Accuracy Run 003 (policy v3, schedule offset)](results/session-suggestions-accuracy-003.md) | Owner acceptance step for ED-0106: merged v2 and v3 policies, v3 with cues and with a true-offset producer override, on the same 28-talk ground truth with the ED-0105 evaluator; whole-day, two-part and independent drift up to ±30 min, five seeds | **PASSED; OVERRIDE CRITERION NOT MET AS WRITTEN IN 1 CASE** - every numeric target met (whole-day ±15 min: 0.93, ≤29 s; ±30 min: 0.89, ≤30 s; two-part ±15 min: 0.93, ≤36 s; independent ±5 min: 0.89, 37/41 s); override within 1.1 s in 7 of 8 cases, 7 s at two-part ±30 min because an override entry cannot split a block; v3 worse than v2 under independent drift ≥ ±10 min (planned limitation) |
| [Boundary cue presets - Cue Run 001](results/boundary-cue-run-001.md) | Owner acceptance step for ED-0107: policy v3 with cue lists composed from the Conference stage profile (catalog v1 defaults, 32 start / 32 end phrases) vs the untuned Run 002 lists, on the Run 003 corpus, models and seeds | **PASSED ON THE TARGETS; PER-CELL COMPARISON MIXED (SMALL)** - every Run 003 target met; better or equal in 12 of 15 cells (e.g. independent ±15 min end error 115 → 56 s); worse in 3 (+0.5 s, +3.3 s, one talk of recall in an untargeted cell) |
| [Session Suggestions - Qualification Run 001 (policy v3, corpus harness)](results/session-suggestions-qualification-001.md) | Phase 5 qualification (ADR-0034 D4): the ED-0114 harness on the 28-talk corpus with one Stage per event day, policy v3 with the Conference stage cue lists, the real published schedule and the whole-day, two-part and independent drift models (five seeds), plus a reproduction check against Run 003 | **TARGET NOT MET** - the harness reproduces Run 003's zero-drift numbers exactly; on the real published schedule no event day meets recall ≥ 0.90 with medians ≤ 30 s (day 3 recall 0.50) because the real error is per talk (durations off by up to 25 min), which v3's one-offset-per-block model cannot represent; 0 wrong-day suggestions in every cell; policy follow-up named, owner prioritization needed |
| [Media timing inspection - Run 001](results/media-timing-inspection-001.md) | Owner host validation of ED-0090: production `ffprobe` inspection of every registered live-run recording into advisory, `unqualified` MTE | **PASSED** - 12/12 succeeded; derived starts exactly 60 s apart in aware UTC (matches reconnaissance); idempotent backfill replay; Kernel facts untouched |
| [Derived Editorial candidates - Run 001](results/derived-editorial-candidates-001.md) | Owner host validation of ED-0092 on the live-run Session: phrase-list publish, human derivation runs, placement recomputation, boundary conflicts, idempotency | **PASSED** - 30 derived candidates with 0 placement mismatches; 1 boundary exclusion recorded; replay idempotent; nothing auto-reviewed |

Future sanitized manifests may be stored under `docs/validation/corpora/`; completed
results are stored under `docs/validation/results/` only when reviewed real values are
available. Large media always remains in a separately controlled external corpus.

## Session Suggestions validation method

Session Suggestions corpus validation uses the pure
[context harness](../../backend/app/contexts/production/session_suggestions/README.md#corpus-validation-harness)
and its JSON manifest schema. Real manifests remain outside the repository. Each run
selects unchanged policy v1/v2/v3 and either the published schedule or a documented seeded
drift model, optionally with catalog-composed cue matches and producer offsets. Matching
is one-to-one at IoU >=0.5 within each Stage. Reports preserve recall, matched start/end
median and p95 errors and within-60 counts, adding scheduled and inclusive precision,
unscheduled count and the +/-12-hour planned-span wrong-day check. Per-seed metrics and
each metric's worst seed are reported; qualification requires the ADR recall/error target
and zero wrong-day suggestions. Synthetic scenario tests pin current behavior without
tuning. The owner separately runs the external corpus qualification and live replay;
this method paragraph records no results.

The [live replay tool](../../scripts/validation/README.md#session-suggestions-live-replay)
copies ordered external blocks into an empty external watched folder at real or accelerated
pace on a disposable review Event and demo database. It polls discovery, enqueues timing
and segmentation through their normal APIs, runs the workers to settlement, and requests
suggestions every N blocks and after the last block. Sanitized reports retain per-run wall
and media elapsed seconds, counts and skips, plus optional per-talk time-to-first-suggestion
and boundary stability using the evaluator's shared one-to-one matcher. Media time is
monotonic replay elapsed time multiplied by pace, anchored to the first block's advisory
timing start; early matches have zero latency, and stability compares successive matches
across absent runs with a strict greater-than-one-second threshold. Final recall and median
edge errors use the existing evaluator. Fake-effect tests require no database or media;
the owner performs the separate synthetic-day replay qualification. No results are recorded here.

## Evidence rules

- Name the exact corpus item and manifest revision without committing its media.
- Record observed results, failures, and limitations; do not convert expectations into
  passes.
- Preserve wall-clock, source-relative, and Session-relative time meanings.
- Link relevant Event-day UX scenarios without rewriting them into implementation claims.
- Omit secrets, DSNs, private absolute paths, and sensitive content.
- Retain checksums or stable external identifiers when appropriate and authorized.
- Distinguish current Kernel results from future intelligence, Editorial, worker,
  Assembly, and automation measurements.
