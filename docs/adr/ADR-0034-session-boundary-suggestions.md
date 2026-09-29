# ADR-0034: Session boundary suggestions from schedule, timing and content evidence

## Status

Proposed (drafted 2026-09-28 at the owner's direction; not accepted). Nothing here is
authorized for implementation until the owner accepts a decision below.

## Date

2026-09-28

## Context

The owner wants StageFlow to *suggest* where each scheduled presentation starts and ends
within continuous stage recordings. Humans review, correct and confirm. Each presentation
must end up as its own Session with its own render.

Accepted authority and implemented capability:

- A **Session** is one actual on-stage presentation or discussion. A **Program
  Expectation** is what the schedule says should happen. It is not proof, and it never
  realizes a Session or sets its boundaries (glossary; ADR-0023; ADR-0024).
- Session realization and boundary correction are human commands. The Kernel stores
  **machine boundary proposals** (`session_boundary_proposal`, migration `0003`). Each is
  a start or end for an *existing* Session, with an advisory epistemic kind, evidence IDs,
  a policy ID and version, and an optional model ID and version. Nothing produces them
  today.
- Media Timing Evidence (ADR-0027, ADR-0033) places each recorder file on the recorder's
  clock. The clock is advisory and unqualified.
- ADR-0026 activates no automatic authority. Automated realization, split and merge are
  an open ADR candidate ("Kernel aggregate evolution").

Real-event evidence examined on 2026-09-28. The owner's archive of a three-day,
multi-stage event is kept outside the repository; this is a sanitized summary.

- **Recorder behaviour:** continuous 10-minute blocks per stage. Recording starts and
  stops a few times a day, for example a lunch gap. Recorder logs give start and stop
  times, duration and dropped frames.
- **Ground truth:** the editor's project gives exact source in/out points for 40
  finished talks. 29 of them come from the main stage over three days, with real recorder
  time. Their structure is:
  - holding content before the day's first talk;
  - a title card held for about 1–2 minutes between talks;
  - changeovers of 1–10 minutes;
  - a lunch gap of about 1.5 hours;
  - a 3-minute opening remark;
  - multi-part sessions of 48–63 minutes.
- **Signals on one real changeover** (talk A ends at 403 s in a block, talk B starts at
  529.6 s):
  - the frame is frozen from 412 s to 527 s (the static title card), with brief breaks at
    436 s and 442 s;
  - audio is silent in stretches from 418 s to 480 s;
  - the freeze ends 3 s before talk B, and starts 9 s after talk A (applause and
    walk-off);
  - freezes during talks from static slides (4–7 s) have no matching silence.

  Measured with FFmpeg's built-in `freezedetect` and `silencedetect` filters at about 5.7×
  real time on the CPU.
- **Clock quality varies:** a second stage's camera files carry a clock two years wrong.
  This is the case the advisory timing model exists for.

## Decision required

1. **Scope of "suggestion":**
   - (a) boundary proposals for Sessions a human has already realized; or
   - (b) also **suggested Sessions**: StageFlow proposes that a scheduled presentation
     happened between two times on a stage, and a human confirms. Confirming realizes the
     Session through the existing human command.
2. **Which evidence** to use first, and whether content analysis is a new Durable
   Operation.
3. **Where suggestions appear:** the Work Queue and Session Detail.

## Options

**Scope**

- **A. Boundary proposals only.** Humans still realize every Session by hand, then
  StageFlow proposes refined start and end times.
  - Smallest change: it uses the existing table and needs no migration.
  - It doesn't meet the owner's goal, where StageFlow suggests the presentations
    themselves.
- **B. Suggested Sessions plus boundary proposals (recommended).** A new advisory
  **Session Suggestion**:
  - Event and Stage, the Program Expectation it matches (or none), a suggested start and
    end, confidence components, evidence IDs, and policy and model lineage;
  - it appears in the Work Queue as "confirm presentation";
  - confirming calls the *existing* human Session realization command with the suggested
    times, recorded as its provenance; rejecting records a decision;
  - after realization, refinements use the existing boundary-proposal table.

  Nothing is realized automatically. ADR-0026 stays inactive.
- **C. Automatic realization under policy.** Rejected for now. It needs ADR-0026 policy
  activation and qualification evidence that doesn't exist yet.

**Evidence, in order of cost**

1. **Schedule:** Program Expectation start and end give a prior window.
2. **Recorder timing:** Media Timing Evidence places blocks on the stage timeline;
   recorder start and stop, and gaps, bound the candidates.
3. **Content changeover signals:** freeze intervals together with silence or low audio
   mark holding and changeover stretches. Measured by FFmpeg's built-in filters in a new
   `media_segmentation` Durable Operation kind on the existing substrate, the ADR-0033
   pattern, using the operator-installed LGPL FFmpeg by explicit path. Outputs are
   advisory intervals with filter parameters as lineage.
4. **Later, optional:** transcript cues (existing phrase-list matching: introductions,
   thanks) and title-card or slide detection.

**Combining evidence**

- A deterministic, versioned policy (no model):
  - snap the scheduled start and end to the nearest changeover edge within a tolerance
    window;
  - mark every suggestion with the evidence used.
- Missing or contradictory evidence yields a lower-confidence suggestion or none.
- The clock stays advisory. A suggestion from an unqualified clock is labelled so, and a
  clock-skew case (a camera date years off) must degrade to schedule-only or content-only
  suggestions and never place media on the wrong day.

## Recommended default

- Scope **B**.
- Evidence **1 + 2 + 3** first, with transcript cues deferred.
- A deterministic `boundary-suggestion` policy v1.
- Suggestions shown in the Work Queue (an additive item type) and on Session Detail.

This needs:

- a small additive schema for Session Suggestions and their decisions, and the
  segmentation evidence (one migration);
- the new operation kind;
- no change to Session authority semantics, because confirmation reuses the existing human
  command.

## Validation approach

- **Ground-truth corpus:** 40 decoded talks. It stays outside the repository; only
  sanitized results are committed.
- **Measure:**
  - presentation detection recall and precision;
  - start and end error: median and 95th percentile, in seconds;
  - behaviour across recording gaps, multi-part sessions and wrong camera clocks.
- **Live-simulation replay:** play blocks into a watched folder at real-time or
  accelerated pace. The corpus supports this.
- **Acceptance target for v1, proposed:** suggestions for at least 90% of talks, with
  median start and end error of 30 s or less, and no suggestion placing media on the wrong
  day.

## Consequences

- StageFlow gains its first content-analysis evidence and its first suggestion workflow.
  Authority stays human.
- CPU or GPU cost for segmentation is roughly one decode per recorded minute. It is
  bounded and can be deferred like media timing.
- The Kernel aggregate evolution candidate stays open for automatic realization, split
  and merge.

## Alternatives considered

- **Model-based detection (speaker or scene ML):** deferred. It needs dependency, licensing
  and GPU decisions, and it offers no obvious gain over deterministic signals for v1.
- **Using the schedule alone:** too coarse. Actual starts drift from the plan, and the
  real edit includes items a schedule may not list, such as opening remarks and multi-part
  sessions. The schedule-to-actual drift has not been measured yet; the validation
  should measure it once the event's schedule is available.
