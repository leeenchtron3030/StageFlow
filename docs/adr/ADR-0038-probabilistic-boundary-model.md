# ADR-0038: Probabilistic boundary model over an event grammar (policy v6)

## Status

Proposed (2026-10-01). This is an owner decision. It extends
[ADR-0034](ADR-0034-session-boundary-suggestions.md) and does not replace its authority model:
suggestions stay advisory, and every Session is realized by a human.

## Date

2026-10-01

## Context

- **Live Replay Run 002** ([result](../validation/results/session-suggestions-replay-002.md))
  ran on one real event-day morning at 1×.
  - Transcript evidence arrives about 2 minutes after each block closes.
  - Live v3 recall is 0.40.
  - Offline v5 reaches recall 1.00, with starts within about 10 s. But its **end edges are
    minutes off** on 3 of 5 talks, and one start jumps to a worse edge as evidence arrives.
  - The owner held the ED-0118 freeze for a v5 end-edge revision.
- **The pattern since v1:** every policy (v1, v2, v3, the parked v4, v5) is a deterministic DP
  over candidate edges. Each new evidence type needed new hand-tuned rules and constants, and
  each fixed one failure mode while exposing another.
  - Qualification Run 001 showed that the real schedule error is *per talk*: lateness that
    accumulates and recovers through the day.
  - Run 002 showed the remaining error is in *ends*, where a talk fades out through Q&A,
    thanks, applause and the MC's return, rather than stopping cleanly.
- **The owner's direction (2026-10-01):** work towards a probabilistic sequence model with
  calibrated confidence. Combine evidence lean-first, and build an approach particular to
  StageFlow, faster and more accurate. Evaluate licences and pitfalls up front
  ([licence and risk review](../security/boundary-evidence-license-review-2026-10-01.md)).
- **Constraints:**
  - offline, on the owner-operated appliance (ADR-0037);
  - no copyleft components;
  - advisory evidence only;
  - domain logic independent of adapters;
  - a deterministic, replayable policy, with the same inputs giving the same outputs.

## Decision required

1. Whether boundary suggestion moves from rule-based edge selection to a **probabilistic
   segmental model** (policy v6), with calibrated per-edge confidence.
2. Which **evidence families** feed it, and in what order.
3. Whether StageFlow accepts a **generic production-signal ingest** for control-plane events.
   This means external inputs from the event's own equipment, which is the first such input
   type.

## Options

- **A. Keep tuning rules (v5.x, v6 as more rules).** Smallest step each time. But constants
  multiply, the end-edge problem recurs with every new evidence type, and there is no
  calibrated confidence.
- **B. A generic HMM per second.** Principled, but tens of thousands of steps per day, a
  geometric (wrong) duration model, and slow online updates. Not selected.
- **C. An event-grammar semi-Markov model over a pruned candidate-edge lattice
  (recommended).** Described below.

## Recommended default (option C)

**C1. The event grammar.** A Stage day is modelled as a sequence of phases, built from the
owner's production experience and the decoded archive:

```
Holding → [ Intro → Talk → (Q&A) → Outro → Changeover ]×N → Holding
```

- Each scheduled Program Expectation contributes one bracketed unit.
- The phases are latent; only the talk span (Intro through Outro) is the suggested Session.
  That keeps ADR-0034's semantics.
- Units may be **skipped** (a cancelled talk) or **unscheduled** (an inserted talk), each at a
  small prior cost. This generalizes v5's program-span rule.

**C2. Explicit-duration priors conditioned on the schedule.**
- **Talk length:** log-normal, centred on the planned duration and widened per event.
- **Changeover and Intro/Outro lengths:** empirical distributions from the owner's archive.
- **The lateness chain:** a talk's start offset from the plan is its predecessor's offset
  plus a small random step. This encodes the per-talk accumulating lateness that Run 001
  measured, and that a single day offset (v3) cannot represent.

**C3. Calibrated evidence as log-likelihood ratios.** Every detector emits timed evidence:
the log-likelihood ratio that a given phase transition happens at time *t*. Each is
calibrated (a logistic fit per detector, with cross-validation by event day) on the owner's
labelled archive. The families, in order of cost:

| Family | Source | Strongest at |
| --- | --- | --- |
| Changeover structure | Existing segmentation: freeze, silence, gap | Changeover ↔ Talk |
| Transcript cues | Existing transcripts and Conference cue lists | Intro, Outro |
| Audio scene | FFmpeg `aspectralstats`, `ebur128` and `astats`, added to the existing decode pass, plus Whisper by-products (no-speech probability, non-speech tokens), scored by small StageFlow-trained heads for **applause, music and speech** | **Outro → Changeover (ends)** |
| Voice continuity | Pooled Whisper encoder states per window, compared with adjacent windows only (no identity, nothing stored) | Talk → Q&A → Outro, the MC's return |
| Picture | FFmpeg `scdet` and `blackdetect`, and similarity to the day's first holding frame | Holding and Changeover |
| Control plane (optional) | Generic production-signal ingest: switcher tally or overlay, mic channel open and close, title-card triggers, one-tap stage-manager marks | Near-exact edges when present |
| Human anchors | Producer confirmations and corrections | Clamp the lattice (C5) |

Missing families contribute nothing. The model degrades to the evidence present, so no
transcript or no control plane still works (ADR-0036 degradability).

**C4. Inference over a pruned lattice (fast).**
- **Candidate edges:** evidence peaks, plan-anchored points, and coverage bounds. That is a
  few hundred per day, not tens of thousands of seconds.
- **Decoding:** an explicit-duration (semi-Markov) Viterbi pass, plus a forward-backward pass
  for the marginals. Each run costs milliseconds.
- **Online use:** each suggestion run decodes the day so far, with a **fixed lag**. An edge is
  marked **settled** once its posterior mass within ±15 s exceeds a threshold. This gives an
  explicit "safe to confirm" signal.
- **Determinism:** fixed-point arithmetic for scores and stable tie-breaking keep it
  replayable. This is the v2 DP lineage, made probabilistic.

**C5. Anchors and learning during the event.**
- A producer confirmation or correction becomes a hard anchor: that edge's time is clamped.
  Because the lateness chain propagates, **one confirmation re-times the rest of the day's
  priors**.
- Detector reliabilities update during the event, by a bounded Bayesian update from anchors.
  This is per Event and versioned in the run's lineage. The global calibration is never
  silently changed.

**C6. Outputs.**
- The existing Session Suggestion contract, plus:
  - per-edge **confidence** (posterior probability within ±30 s);
  - a **settled** flag;
  - the top contributing evidence ("why").
- The producer UI shows **only uncertain or unsettled edges as exceptions**, following the
  owner's rule that the UI is scannable under load.
- Policy lineage: version `6`, model ID and version, calibration digest, prior digest.

**C7. Control-plane ingest (decision 3).**
- One read-only, authenticated local endpoint (HTTP, optionally OSC) accepts typed production
  signals, such as:
  - `program_input_changed`;
  - `overlay_on` / `overlay_off` (title card, lower third);
  - `mic_open` / `mic_closed`;
  - `stage_mark`.
- Each signal carries an operator-assigned meaning per Event.
- The operator's Bitfocus Companion (MIT, separate) bridges vMix, ATEM and consoles to it. A
  direct vMix TCP adapter is an optional later addition.
- No vendor SDK is bundled. Signals are evidence, never commands.

## Why this is StageFlow-specific

- **The schedule-conditioned lateness chain** (C2) captures how real event days drift.
  Generic segmentation models assume nothing about a published plan.
- **The phase grammar** (C1) and the detector heads are **learned from the owner's own decoded
  productions**. That makes them licence-clean and tuned to how live event stages actually
  run (MC handoffs, title cards, walk-on music, applause), not to broadcast TV.
- **It reuses what the chain already computes:** the existing FFmpeg decode pass and the
  Whisper engine. So the new evidence adds little latency, which matters, given that
  transcripts take about 2 minutes.
- **Confidence and settled edges** turn accuracy into producer trust. StageFlow says when it
  is sure.
- **One confirmation re-times the day** (C5). Human effort compounds instead of fixing one
  talk at a time.

## Validation approach

- **Offline first:** a harness on all three corpus days, plus the Live Replay Run 002 evidence
  timeline, using its D5 "evidence available at each run's time" method. Measures:
  - recall;
  - median and p95 start and end error at +5 min, +15 min and final;
  - edge stability;
  - **calibration** (reliability of the confidence values);
  - the producer-attention rate (the fraction of edges flagged as exceptions).
- **Gate for v6 to replace v5 as default:**
  - per event day, recall ≥ 0.90 with median start and end error ≤ 30 s at +15 min;
  - no talk worse than v5 by more than 60 s at +5 min;
  - calibration error ≤ 0.10;
  - no wrong-day suggestion.
- **Day-level cross-validation:** never train and evaluate on the same day. Held-out
  synthetic seeds stay unused.
- **A replay run (Run 003)** before any default switch.

## Consequences

- Policy work moves from hand rules to calibrated evidence and priors. Constants become
  fitted parameters with recorded provenance.
- The archive becomes a training asset, which needs the owner's confirmation of contractual
  rights (licence and risk review, open item 1).
- New evidence families follow one pattern (a detector plus calibration). Adding one never
  needs new edge rules.
- **v5 stays the near-term path.** Its end-edge revision can use the Phase A and B evidence
  first, and the ED-0118 freeze can proceed on it. v6 replaces v5 only after its own gate.

## Alternatives considered

- **Deep end-to-end segmentation**, for example a transformer over the whole day. Data-hungry
  (29 labelled main-stage talks), opaque, hard to keep deterministic, and not clearly
  licence-clean if pretrained. Not selected.
- **Third-party audio-event and speaker models as defaults.** Licence-ambiguous (YouTube-derived
  training data) and biometric if identifying. Kept as optional comparisons only.
- **Automatic realization.** Out of scope. ADR-0026 stays inactive.
