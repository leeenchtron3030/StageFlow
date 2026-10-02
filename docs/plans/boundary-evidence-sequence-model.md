# Boundary evidence and the probabilistic sequence model (ADR-0038)

## Status

**Approved** (owner, 2026-10-01): ADR-0038 accepted, D1–D6 approved, and **ED-0126 to ED-0130
allocated** as listed in the phases below. The owner also approved, the same day:
- adding a language-model edge referee to the Phase A lab;
- the corpus additions under Phase A.

## Execution authority

- **Classification:**
  - **Phase A** (offline evidence measurement) is Green once approved.
  - **Phases B and C** are pure policy and harness work, Green after ADR-0038.
  - **Phase D** (production-signal ingest) adds an external input type. It needs ADR-0038
    decision 3 accepted.
  - **Phase E** (v6 persistence and UI) involves a migration, under an approved plan.
- **Authority evidence:**
  - ADR-0034 (suggestions, advisory);
  - ADR-0036 (transcription, degradable);
  - ADR-0037 (appliance);
  - the Live Replay Run 002 result and the owner decision to hold ED-0118 for a v5 end-edge
    revision;
  - the owner's 2026-10-01 direction towards a probabilistic sequence model;
  - the [licence and risk review](../security/boundary-evidence-license-review-2026-10-01.md).
- **Implementation-ready:** yes, phase by phase. Phase D still needs its own directive before
  implementation.

## Problem statement

v5 gets recall and starts right but misses ends by minutes on the real day (Run 002). Every
past policy step added hand-tuned rules for one failure mode. StageFlow needs:
- evidence that targets how talks *end*;
- one model that combines all evidence with calibrated confidence;
- a lean path that delivers value at each step.

## Decisions (recommended defaults)

- **D1. Measure before building.** Every new evidence family is first extracted offline on the
  archive and scored for how far it separates true edges from non-edges. Only families that
  measurably help are productized.
- **D2. Reuse before adding.** Evidence comes first from instruments already in the chain:
  - FFmpeg statistics on the existing decode pass;
  - Whisper by-products from the ED-0122 engine.

  Third-party audio and speaker models are comparisons only (the licence review).
- **D3. Train on the owner's archive.** Small, calibrated heads are trained on the owner's
  decoded productions, with labels derived from ground-truth edges. Cross-validate by day.
  Training data stays off the repository.
  - **Rights:** the owner confirmed on 2026-10-01 that the archives and links they supply may
    be used for this internal purpose.
  - **Labels:** Phase A extends them automatically to a second event day. Its edited exports
    exist (ordered talks with the standard opening graphic and music cue). Audio
    cross-correlation locates each export in the raw blocks, as was done for the first
    corpus. No manual labelling is needed.
- **D4. No identity.** Voice evidence is same-session continuity only: no enrollment, no
  stored embeddings, no named speakers.
- **D5. v5 first, v6 next.**
  - The owner-decided v5 end-edge revision uses Phase A and B evidence where it helps. Then
    ED-0118 freezes v5.
  - v6 is developed offline in parallel, and replaces v5 only through its own gate (ADR-0038
    validation).
- **D6. Production signals come from the recording software.**
  - Read-only adapters for the **vMix TCP API** and **OBS WebSocket v5**: the software that
    writes the blocks in most live productions (owner, 2026-10-01).
  - Hardware switchers and consoles are not a design target.
  - No vendor SDKs. A generic endpoint for optional manual marks.

## Phases

| Phase | Proposed ED | Deliverable | Kind | Exit criterion |
| --- | --- | --- | --- | --- |
| **A. Evidence lab** | ED-0126 | Automatic ground truth from export-to-block audio cross-correlation (local only) for the 2024 edition (three days), the 2023 single-room summit and, if alignment is clean, a 2023 two-track event; families added to the lab: **known-graphics (title-card) matching**, **music-cue matching**, and a **language-model edge referee** (a local Apache-2.0 or MIT model, grammar-constrained, choosing sentence indices in targeted windows only); `scripts/validation/boundary_evidence_lab.py`: offline extraction on archive blocks of FFmpeg `aspectralstats`, `ebur128`, `scdet` and `blackdetect` per second; Whisper no-speech probability, non-speech tokens and pooled encoder states per window; plus a separability report per family against the ground-truth edges (ROC AUC and detection lead/lag) | Validation tooling; no product change | A sanitized result ranks the families by how well they separate ends and starts |
| **B. End evidence and v5 end revision** | ED-0127 | Small applause, music and speech heads, plus a voice-continuity score (owner-archive trained, calibrated); a v5 end-edge revision (pure policy) using the evidence that passed A; an offline D5-style evaluation on 3 days and Run 002 | Pure policy plus harness | v5-revised meets D5 (no talk worse at +5 min) and improves end medians on all days; then **ED-0118 freezes it** (migration 0028) |
| **C. v6 offline** | ED-0128 | A pure domain module: event grammar, explicit-duration priors with the lateness chain, LLR calibration, lattice semi-Markov decoding with marginals, settled flags, anchors; harness `--policy-version 6` | Pure policy plus harness | ADR-0038 gate met offline on all days and on Run 002's timeline, including calibration ≤ 0.10 |
| **D. Recording-software signals** | ED-0129 | Read-only vMix TCP (TALLY, ACTS, XML) and OBS WebSocket v5 (scene, scene-item, mute, media-playback, record-file events) adapters; per-Event signal-meaning mapping; persistence as advisory evidence; a generic endpoint for manual marks | Adapters plus migration; needs ADR-0038 decision 3 | A rehearsal with vMix and with OBS: signals land as evidence with correct times, and v6 uses them offline |
| **E. v6 in product** | ED-0130 | Persist new evidence (from A and B) and v6 runs, with confidence and settled flags; producer UI shows exceptions only; Live Replay Run 003 | Migration, service, UI | Run 003 at 1× meets the ADR-0038 gate; owner UX checkpoint; default switch |
| **F. Optional, measured** | later | OCR of title cards and lower thirds, matched to the schedule; picture embeddings; a local Apache-2.0 or MIT LLM labelling transcript windows | Each measured in the Phase A lab first | Only if the lab shows a gain |

**Sequencing.**
- A then B is the critical path to ED-0118.
- C can start once A's features exist.
- D is independent and can run in parallel once ADR-0038 decision 3 is accepted.
- E follows C, and D where available.

## Language-model edge referee (Phase A test, approved 2026-10-01)

- **Role: refinement, never the source of truth.** It runs only on edges v6 marks uncertain:
  unsettled, low-confidence, or with two close candidates.
- **Input:** about ±3 minutes of transcript, with word timings, plus the schedule entry and the
  candidate edges. That is about 1,500–2,000 tokens.
- **Output:** a grammar-constrained answer that picks sentence indices and labels sections
  (intro, talk, Q&A, MC handoff, break). **It never writes times;** times come from word
  timestamps.
- **Use:** its answer becomes a calibrated evidence input to v6.
- **Determinism and audit:** temperature 0, a pinned model checksum and runtime, and answers
  stored as evidence keyed by input digest, so replays reuse them.
- **Cost:** a 4-bit 7B model needs about 5 GB of GPU memory and takes about 1–2 s per edge, so
  tens of GPU-seconds per day. There is no per-use cost.
- **Licences:** Qwen2.5 7B or 14B (Apache-2.0), or Phi-3.5-mini (MIT), on llama.cpp (MIT).
  **Not Qwen2.5-3B** (non-commercial).
- **Ships only if** the Phase A lab shows it adds accuracy on ends beyond the cheaper families.

## Lean-first rationale

- **A** costs one script and a few GPU hours on the archive. It tells us which families are
  worth anything before any product change.
- **B** directly attacks the measured failure (ends), and unblocks ED-0118 with evidence-backed
  rules.
- **C** reuses the existing harness, manifests, evaluator and D5 method. The model is pure
  domain code with no new runtime dependency (numpy is already in `transcription-core`; the
  domain itself should stay plain Python and fractions where determinism matters).
- **D** gives near-exact edges when the gear is reachable, at the cost of one endpoint, because
  Companion does the per-vendor work.

## In scope (whole plan)

- Offline lab, detectors, v5 revision, v6 module and harness, production-signal ingest,
  persistence of evidence and v6, UI exceptions, and replay validation.
- Directly affected docs: ADR-0034 and ADR-0038 records, architecture docs, glossary terms
  (*production signal*, *edge confidence*, *settled edge*), and operator READMEs.

## Out of scope

- Automatic Session realization (ADR-0026 stays inactive).
- Speaker identification, face recognition, or any biometric identity.
- Cloud services; any network dependency during an Event.
- Bundling vendor SDKs or Companion.
- Third-party audio and speaker models as shipped defaults.

## Constraints

- Offline. No copyleft in what ships. Licences recorded per the review.
- Deterministic, replayable policy with recorded lineage: model, calibration and prior digests.
- Advisory evidence only. Missing families degrade gracefully.
- No real media, transcripts, names or schedules in the repository. Sanitized results only.
- The domain stays independent of FFmpeg, Whisper, Companion and the API.

## Risks and catches

| Risk | Mitigation |
| --- | --- |
| A small labelled corpus (29 main-stage talks plus the Day 2 legacy material) risks overfitting | Day-level cross-validation; few parameters (logistic heads, low-parameter priors); hold out Run 002's morning for v6 |
| Applause-like noise (audience chatter, room tone) causes false ends | Calibrated LLRs combined with the grammar: an "end" also needs a changeover or voice change soon after |
| Whisper non-speech tokens hallucinate | Weight them weakly through calibration; never used alone |
| vMix or OBS API changes between versions | Pin the tested versions per appliance profile; adapters optional and isolated; signals are evidence only |
| Contractual rights to train on client footage | Confirmed by the owner on 2026-10-01 for internal use |
| LGPL-3.0 FFmpeg installation-information duty | Applies only to consumer "User Products"; recorded in the review; revisit if the appliance is sold or leased |
| Confidence miscalibration erodes producer trust | Calibration is part of the gate; the UI shows confidence only after calibration passes |
| Latency growth | Features computed in passes that already run; lattice decoding takes milliseconds; measured in Run 003 |

## Acceptance criteria

- [ ] ADR-0038 accepted (decisions 1–3) and this plan approved, with ED numbers allocated.
- [ ] Phase A result recorded: families ranked by separability.
- [ ] Phase B: v5-revised meets D5 offline; ED-0118 completed.
- [ ] Phase C: the v6 offline gate is met.
- [ ] Phase D: the production-signal ingest rehearsal is recorded (if pursued).
- [ ] Phase E: Live Replay Run 003 meets the gate; owner UX checkpoint; default switch.

## Rollback

- Phases A to C are tooling and pure policy, reverted by reverting the code.
- D and E are additive. v5 stays selectable, and the default switch is reversible by
  configuration of the policy version.

## Open questions for the owner

- None blocking. Answered on 2026-10-01:
  - training rights are confirmed for internal use;
  - production signals focus on vMix and OBS;
  - the second day is labelled automatically from its exports (Phase A).
- **A later, separate decision:** whether a recorder-reported file closure (OBS or vMix) may
  count as a strong readiness finalization method (ED-0049).
