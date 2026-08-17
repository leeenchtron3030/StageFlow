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
| [Real-Event Playback Validation and UX Calibration](../plans/real-event-playback-validation.md) | Current-Kernel direct/vMix replay runbook, measurements, UX calibration, and future reuse | Run 002 passed; Run 003 invalid; Run 004 partially qualified turnover |
| [Run 004 qualification-tooling hardening](../plans/run-004-qualification-tooling-hardening.md) | Turnover authority guard, host-local lock, atomic evidence, incremental checkpoints, and runtime protection | Green qualification-only hardening validated and used by Run 004 |
| [Run 004 qualification closure and timing telemetry](../plans/run-004-qualification-closure.md) | Immediate authority timestamp capture, source-aware runtime telemetry, and partial qualification closure | Green qualification-only closure completed and validated |
| [vMix media timing evidence reconnaissance](vmix-media-timing-reconnaissance.md) | Sanitized read-only Run 004 container, stream, packet, and candidate-interval findings | Green reconnaissance complete; production authority not qualified |
| [vMix media timing calibration experiment](vmix-media-timing-calibration.md) | Controlled experiment for measuring recorder timing against independent content markers | Harness self-check complete; controlled vMix execution not run |
| [Recorder calibration harness](recorder-calibration-harness.md) | Deterministic marked-source generation, decoded content-boundary analysis, and controlled vMix runbook | Tooling implemented/self-checked; vMix qualification not run |
| [Recorder calibration harness self-check](results/recorder-calibration-harness-self-check.md) | Sanitized FFmpeg source/60s/30s/partial fixture evidence and limitations | Qualification-tool readiness PASS; recorder qualification NOT RUN |
| [Media timing qualification probe](../../backend/tests/qualification/media_timing_probe.py) | Bounded local inspection with sanitized raw observations and explicitly unqualified derivations | Implemented qualification tooling; prohibited from authority use |
| [Bounded real-event playback runner](../../backend/tests/qualification/real_event_playback.py) | Explicit validation-only commands, bounded cycle cadence, retained identities, atomic local results, and reconstruction | Implemented qualification tooling; not a watcher or public API |
| [Safe local validation controller](../../scripts/validation/README.md) | PowerShell wrapper, Run-isolation safeguards, action map, and guarded Run 004 same-Stage procedure | Hardened qualification tooling; Run 004 not started |
| [Reference-corpus manifest example](reference-corpus-manifest.example.yaml) | Human-readable, diffable corpus and ground-truth annotation shape | Example only; not a runtime schema |
| [Playback-run result template](real-event-playback-run-result-template.md) | Sanitized evidence record for one direct or vMix run | Reusable template |
| [Run 002 — real-media Durable Event-Mode Kernel baseline](results/real-event-playback-run-002.md) | Sanitized real-media, Session/package, reconstruction, finding, performance, and UX evidence | **PASS — Real-media Durable Event-Mode Kernel baseline** |
| [Run 003 — invalid same-Stage turnover execution](results/real-event-playback-run-003.md) | Sanitized missing-Session authority, conservative media preservation, and qualification-tooling incident evidence | **INVALID — intended same-Stage turnover qualification not executed**; secondary conservatism diagnostic pass |
| [Run 004 — same-Stage turnover partial qualification](results/real-event-playback-run-004.md) | Sanitized lifecycle, media, association-policy, authority-latency, and runtime-estimator evidence | Lifecycle/preservation/policy **PASS**; content-correct automatic association **INCONCLUSIVE / NOT QUALIFIED** |

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
