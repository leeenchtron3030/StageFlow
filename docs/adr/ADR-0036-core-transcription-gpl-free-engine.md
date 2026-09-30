# ADR-0036: Core transcription with a GPL-free engine

## Status

Accepted (owner, 2026-09-30).

When implemented, it supersedes the deferral recorded by ED-0075, which is option 3 of the
[2026-08-21 SBOM record](../security/dependency-license-sbom-2026-08-21.md#decision-options-for-the-pyavffmpeg-exposure).
Until the GPL-free engine is merged and qualified, ED-0075's exclusion stays in force.

## Date

2026-09-30

## Context

- **Transcription is optional today.** The accepted first provider (2026-08-18) is
  faster-whisper 1.2.1 on CTranslate2, behind the provider-neutral Work Execution port
  ([transcription evidence readiness](../architecture/transcription-evidence-readiness.md)).
  ED-0075 keeps the `transcription` dependency group optional and operator-installed, and
  excludes it from every distributable artifact.
- **The reason is a confirmed GPL build.** The PyAV wheel that faster-whisper requires
  bundles an FFmpeg built with `--enable-gpl` (libx264 and libx265 are vendored). This was
  confirmed on 2026-08-28.
  - StageFlow uses PyAV only through faster-whisper, to **decode** audio. The adapter
    passes a media path (`backend/app/infrastructure/transcription/faster_whisper.py`).
  - No StageFlow code imports PyAV directly.
  - Rendering uses an operator-supplied FFmpeg binary at an explicit path.
- **PyAV can't be removed simply by decoding elsewhere.** faster-whisper accepts
  in-memory audio arrays, but it imports `av` at module import (`faster_whisper/audio.py`)
  and declares `av` as a hard requirement.
- **Transcript cues have become central evidence.** Policy v5 (ADR-0034 Phase 7, ED-0117)
  gets most of its accuracy gain from them:
  - with a perfect schedule, recall is 1.00 on all three corpus days, against v3's
    1.00 / 0.91 / 0.88;
  - on the real published schedule, day 3's start error falls from 215 s to 34 s with the
    chosen constants.
- **Owner direction (2026-09-30):**
  - StageFlow is **operated by the owner and their team**, and tailored per event; it is
    not handed to clients;
  - it runs on an owner-operated GPU appliance (ADR-0037);
  - transcription should be **on by default**;
  - the design should **avoid the need for legal review**;
  - English only is acceptable.
- **The existing clean pattern:** timing and segmentation (ADR-0027 and ADR-0033) run an
  operator-supplied **LGPL FFmpeg binary at an explicit path**, in a separate process.

## Decision

1. **Transcription is a core StageFlow capability, on by default.**
   - Every production deployment includes it, and new Events enable it.
   - It remains **degradable**. When transcription is unavailable, disabled for an Event,
     or behind the live edge, suggestion runs proceed on the other evidence: v5 without
     cues equals v3 plus the coverage and program-span rules.
   - It never blocks media discovery, registration, timing, segmentation or Session work.
2. **The shipped transcription engine is GPL-free by construction**, so no legal review is
   needed.
   - **Decode:** the operator-supplied LGPL FFmpeg binary, at an explicit path, as a
     separate process. It produces 16 kHz mono PCM.
   - **Inference: option A (default).** A thin StageFlow-owned adapter over **CTranslate2**
     (MIT) runs the same Whisper model family as today. It may adapt the MIT-licensed
     faster-whisper logic, but it must not import `faster_whisper.audio` or PyAV.
   - **Inference: option B (fallback).** **whisper.cpp** (MIT) as an external binary at an
     explicit path. It is chosen only if the engine spike shows A cannot meet the latency
     budget on the appliance GPU.
   - **PyAV and the GPL FFmpeg wheel leave the dependency set.** The `transcription`
     group is replaced by the GPL-free engine's dependencies, which are MIT or Apache
     licensed and listed in a regenerated SBOM.
3. **Parity and latency gate the switch.** Before the new engine replaces faster-whisper,
   a bounded spike on real blocks must show:
   - word-timestamp and cue-hit parity with the current transcripts, within stated
     tolerances;
   - seconds of processing per 10-minute block on the appliance-class GPU, including
     while a render is running.
4. **Models are provisioned offline.** Whisper model weights (MIT) are installed on the
   appliance before an Event, versioned and verified by checksum. No network is needed in
   Event mode.
5. **Scope:** English only for v1.
   - Language detection is fixed to English unless an Event overrides it.
   - Diarization, translation and cloud providers are out of scope.
   - The provider-neutral port stays in place, so another engine is a separate decision.

## Alternatives

- **Keep ED-0075 (operator-installed, excluded).** This contradicts "on by default" and
  leaves the core evidence optional. Rejected.
- **Own an LGPL-only PyAV and FFmpeg build (SBOM option 1).** It is GPL-free with no code
  changes, but StageFlow would own native builds, patching and reproducibility for each
  platform. That is heavier to maintain than option A. Not selected.
- **Ship the current GPL wheel after counsel review (SBOM option 2).** It is simplest to
  engineer, but it requires legal review, which the owner asked to avoid. Rejected.
- **Owner operation only, arguing there is no distribution.** Likely valid, but it depends
  on the operating model never changing: leasing or selling an appliance would reopen the
  question. The GPL-free path costs little and removes that dependency. Not selected as
  the basis.

## Consequences

- **Transcription becomes part of the live chain's latency budget.** The replay and
  qualification must measure it (the ED-0115 replay extension, and Live Replay Run 002).
- **The GPU is shared** by transcription, NVENC rendering (ADR-0029) and possibly
  segmentation. Worker capability and scheduling must budget it (ADR-0037).
- **The engine is StageFlow's to maintain.** The option A adapter is small, but StageFlow
  owns it, including its tests against upstream CTranslate2 changes.
- **ED-0075's guard and documentation are updated** when the GPL-free engine lands, and
  the SBOM is regenerated.
- **Earlier transcripts stay valid** as immutable provider results with their recorded
  provider identity. The new engine records its own provider identity and version.

## Validation

- **Engine spike (proposed ED-0119):** option A, and optionally B, against the current
  faster-whisper on real blocks (local, never committed). It measures:
  - word-timestamp deltas and cue-hit agreement on the Conference stage lists;
  - seconds per 10-minute block on the GPU and on CPU;
  - behavior with a concurrent NVENC render.
- **SBOM regeneration:** no GPL or AGPL component in the shipped dependency set, and the
  FFmpeg binary is recorded as LGPL.
- **Live Replay Run 002** with transcription in the chain: a half day of real blocks at
  1×.

## Related documents

- [ADR-0027](ADR-0027-media-timing-evidence.md) and
  [ADR-0033](ADR-0033-production-media-timing-inspection.md): the explicit-path LGPL
  FFmpeg pattern.
- [ADR-0029](ADR-0029-nvenc-rendering-and-gpu-worker-requirement.md): the GPU worker
  requirement.
- [ADR-0034](ADR-0034-session-boundary-suggestions.md): transcript cues as boundary
  evidence.
- [ADR-0037](ADR-0037-owner-operated-gpu-appliance-baseline.md): the deployment baseline.
- [SBOM record](../security/dependency-license-sbom-2026-08-21.md), and the ED-0075
  [plan](../plans/transcription-distribution-boundary.md).
- [Transcription evidence readiness](../architecture/transcription-evidence-readiness.md).
