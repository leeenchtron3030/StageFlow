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

Future sanitized manifests may be stored under `docs/validation/corpora/`; completed
results are stored under `docs/validation/results/` only when reviewed real values are
available. Large media always remains in a separately controlled external corpus.

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
