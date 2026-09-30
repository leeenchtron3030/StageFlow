# Session boundary suggestions (ADR-0034)

## Status

Approved (2026-09-28). Phase 1 (ED-0103) and Phase 2 (ED-0104) are complete. Phase 2b (ED-0105,
policy v2) is detailed below (2026-09-29), after the early accuracy check. After Accuracy Run 002, the owner chose Option B (Phase 2c, ED-0106, Approved 2026-09-29) and asked for Option C to be planned (Phase 2d, outline). Phases 3–5 are outlined here; each gets a detailed section, reviewed by the owner, before it starts.

## Execution authority

- Classification: Green for Phase 1 under the accepted ADR. Later phases are Green once
  their detailed sections are approved.
- Phase 2b continuation: Green and implementation-ready under the approved ED-0105
  section, the overlap clarification merged in `b4a9e1a` / `d6e05f4`, and the owner's
  second-stop decision below. The bounded implementation and synthetic validation are
  authorized; Accuracy Run 002 remains an owner acceptance step.
- Authority evidence:
  - [ADR-0034](../adr/ADR-0034-session-boundary-suggestions.md), accepted by the owner on
    2026-09-28: scope B, transcript cues in v1, and the v1 quality target;
  - ADR-0025 (Durable Operations), ADR-0027 and ADR-0033 (advisory media timing, the
    explicit-path LGPL binary pattern), ADR-0023 and ADR-0024 (human Session authority),
    ED-0092 (phrase matching).
- Required escalation, any phase: stop if the work would need:
  - automatic Session realization or boundary authority;
  - a change to Session, association, package or Program Expectation semantics;
  - a new dependency;
  - committed real-event media, names or paths;
  - a model-based detector.
- Engineering Directives: **ED-0103** is Phase 1. The owner delegated ED numbering; later
  phases take the next free numbers when they are detailed.

## Phases

| Phase | Outcome | Migration |
| --- | --- | --- |
| **1. Media segmentation evidence (ED-0103)** | Advisory freeze and silence intervals per Completed Media Asset, from a new `media_segmentation` Durable Operation | `0021` |
| 2. Session Suggestions core | Suggestion aggregate, deterministic `boundary-suggestion` policy v1 (schedule, timing, segmentation, transcript cues), human-invoked suggestion run, confirm and reject commands (confirm reuses the existing human Session realization and boundary commands) | `0022` |
| 3. Boundary proposals for realized Sessions | The same policy produces `session_boundary_proposal` rows (existing table) for confirmed Sessions | none expected |
| 4. Producer surfaces (ED-0109 backend, ED-0110 Stage page; Completed; follow-up ED-0111 Proposed) | Work Queue item "confirm presentation" (additive, one per Stage), latest-run read, Suggested presentations panel on the Stage page with confirm/adjust/reject and schedule offset, Mission Control summary line; UX checkpoint | none |
| 2c. Policy v3, schedule offset (ED-0106, Completed) | Per-block schedule offset (estimated or producer override) before v2 alignment; Stage offset override setting | `0024` |
| 2d-1. Cue phrase presets and composition (ED-0107 backend, ED-0108 Event page; Completed) | Built-in catalog v1, human composition command publishing the Event's start and end cue lists, runs default to them, Event page section | `0025` |
| 2d-2. Transcript cues as edges (outline) | Policy v4 with `cue` edges | to be detailed |
| 5. Validation harness and Run 001 | Replay the ground-truth corpus (outside the repo) and measure recall, precision and start/end error against the ADR target; sanitized result | none |

## Phase 1: media segmentation evidence (ED-0103)

### Verified current behavior

- **The ADR-0033 media timing inspection is the template:**
  - a `media_timing` operation kind (migration `0017`);
  - an explicit-path LGPL `ffprobe` adapter with an identity check and a demuxer
    allowlist;
  - a CPU worker (`backend/app/demo/media_timing_worker.py`);
  - bounded, idempotent, default-off enqueue (`[local_media_timing]`, the ED-0096
    amendment);
  - advisory evidence with lineage.
- **The FFmpeg render adapter** (`backend/app/infrastructure/rendering/ffmpeg.py`) already
  has the explicit-path FFmpeg identity check (refuses GPL and nonfree builds), argument
  construction without a shell, heartbeats and demuxer allowlists.
- **Real-footage measurement (2026-09-28):**
  - Filters: `fps=5,scale=320:-2,freezedetect=n=0.003:d=4` and
    `silencedetect=n=-40dB:d=3`.
  - Speed: about 5.7× real time on the CPU for a 10-minute 1080p block.
  - Result: freeze and silence intervals bracketed a changeover within 3–9 s of the
    ground-truth boundaries.

### Desired behavior

- **Operation:** a new Durable Operation kind **`media_segmentation`** on the shared
  substrate.
  - The work key is the asset, the manifest and the segmentation profile ID and version.
  - Other operation kinds are unchanged, and each kind's constraints stay exact for that
    kind, following the ADR-0032 amendment 2 rule.
- **Profile v1** (constants, recorded as lineage): the filter chain and thresholds above,
  CPU decode, and the demuxer allowlist.
- **Worker:** a CPU worker using the operator-installed FFmpeg by explicit path (a new
  `[local_media_segmentation]` config section: `enabled`, `ffmpeg_path`). It runs both
  filters in one pass and parses `freeze_start`/`freeze_end` and
  `silence_start`/`silence_end`. Only bounded numeric values are kept; stderr text is
  never stored.
- **Evidence:** immutable per asset and operation.
  - Each interval records kind (`freeze` or `silence`), start and end offsets in integer
    microseconds from the asset start, and the profile ID and version.
  - An asset has at most 10,000 intervals. Exceeding that is a typed failure, not
    truncation.
  - Evidence is advisory, with no authority.
- **Enqueue:** default off, bounded at 100 per cycle, and idempotent by work key, for
  registered Event assets lacking a segmentation operation. This is the ED-0096 pattern.
  An explicit human backfill command is also provided.
- **API:** a bounded read of segmentation evidence per asset and per Session.
- **Failure mapping:** reuse the render and timing typed codes where they fit (identity
  refused, input missing, non-zero exit retryable, output invalid). New codes only as
  needed, and listed.

### In scope

Migration `0021` (forward and reverse); contracts; the adapter; the worker and its
config; enqueue and backfill; repository (memory and PostgreSQL); API read; tests;
documentation (glossary term "Media Segmentation Evidence", capability layer, config
README).

### Out of scope

The Phase 2 policy and suggestions, transcript cues, UI, title-card detection, GPU decode,
and any change to media timing, rendering or transcription.

### Constraints

- Identity check and argument safety are the same as the render adapter. No caller text
  in arguments. `shell=False`. Demuxer allowlist.
- Offline. No new dependency. No media content or paths are stored. Aware timestamps from
  the injected clock.
- Every existing constraint stays exact for its operation kind. The reverse migration
  refuses while segmentation rows exist.

### Test strategy

- **Fake-binary tests:**
  - argument construction and parsing of freeze and silence output, including edge cases:
    an interval open at end of file, no intervals, and malformed lines;
  - failure mapping;
  - the interval cap;
  - heartbeats.
- **PostgreSQL:**
  - migration forward and reverse, including the reverse refusing while rows exist;
  - work-key idempotency;
  - bounded enqueue;
  - evidence immutability and reads;
  - other operation kinds unaffected.
- **Real FFmpeg check** (owner step on the host): run the worker on synthetic clips with
  known freeze and silence spans. **Fake binaries cannot prove filter semantics**, the
  lesson from ED-0098. Record a sanitized Segmentation Run 001, including one real-corpus
  changeover compared with ground truth.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

### Acceptance criteria

- [ ] Segmentation operations run end to end and store advisory freeze and silence
  intervals with profile lineage. Every other operation kind is unchanged.
- [ ] Migration `0021` forward and reverse tests pass. The demo database is backed up
  before it is applied.
- [ ] All checks pass on the host. The owner's real-FFmpeg run is recorded.

### Rollback

Revert the code. Reverse `0021` only while no segmentation rows exist.

## Phase 2: Session Suggestions core (ED-0104)

### Verified current behavior

- **Human Session realization:** the Kernel command `start_session(StartSessionRequest)`
  takes the Event, Stage, actor, aware `authoritative_start`, an optional
  `program_expectation_id` and an optional title. The end is set by
  `correct_session_boundary(boundary_kind="end", …)`. Both are idempotent by operation ID
  (`event_mode_kernel/service.py:187-215`).
- **Program Expectations:** `list_program_expectations(event_id)` returns revisioned
  records with an optional `stage_id`, `planned_start` and `planned_end` (aware), title,
  speakers and lifecycle state (`events/kernel_contracts.py:172`). Withdrawn
  expectations must not be selected for new realization (glossary).
- **Timing:** each asset's Media Timing Evidence gives a derived
  `creation_time_plus_duration` interval on the recorder clock, with a qualification. It
  is advisory and currently unqualified (ADR-0027, ADR-0033). ED-0091 and ED-0092 already
  place asset-relative offsets on that clock this way (`editorial/derivation_service.py`,
  `place_match`).
- **Segmentation:** ED-0103 stores per-asset freeze and silence intervals in integer
  microseconds from the asset start, with profile lineage (`media_segmentation_evidence`).
  [Segmentation Run 001](../validation/results/media-segmentation-001.md) observed that
  changeovers can carry audio.
- **Transcript cues:** ED-0092's `match_phrases` over the latest complete Transcription
  Evidence and Event-scoped, versioned phrase lists (`editorial_phrase_list`).
- **Real-corpus shape** (sanitized, from the decoded ground truth):
  - title-card holds of about 1–2 minutes between talks, with brief freeze breaks;
  - changeovers of 1–10 minutes;
  - recorder stops around lunch;
  - freezes of 4–7 s inside talks (static slides) with no matching silence.

### Desired behavior

**Suggestion run (human-invoked)**

- A human starts a run for one Event and Stage, optionally naming a start-cue list and an
  end-cue list (phrase list ID and version).
- The run is idempotent by an input digest covering:
  - the policy ID and version;
  - the Stage's current Program Expectation IDs and revisions;
  - the assets' timing-evidence IDs and revisions;
  - the segmentation evidence IDs;
  - the transcript revisions;
  - the cue-list versions.
- The run records bounded skip counts: `no_timing_evidence`, `no_segmentation`,
  `clock_implausible`, `no_coverage` and `no_planned_time`.

**Policy `boundary-suggestion` v1** (deterministic, pure, no model; constants are
lineage)

1. **Stage timeline:**
   - each asset is placed on the recorder clock by its latest active timing evidence;
   - recorder coverage is the union of placed assets;
   - segmentation and cue offsets are mapped to absolute time the same way.
2. **Clock plausibility:**
   - an asset is used only if its placed interval overlaps the Stage's planned span (the
     earliest planned start minus 12 h to the latest planned end plus 12 h);
   - otherwise it is excluded and counted as `clock_implausible`, and never placed on
     another day;
   - if no Program Expectation has planned times, every asset with timing evidence is
     used, and only unscheduled suggestions (step 7) can result.
3. **Changeovers:**
   - freeze intervals separated by 15 s or less are merged;
   - a merged freeze of at least 30 s is a changeover, and so is a coverage gap of at
     least 30 s;
   - the start and end of coverage are also changeover edges;
   - silence overlap and nearby cue matches are recorded as supporting components, not
     required.
4. **Match each current, non-withdrawn Program Expectation with planned times,** in
   planned order:
   - suggested start = the changeover end nearest `planned_start` within ±20 min;
   - suggested end = the changeover start nearest `planned_end` within ±20 min, and more
     than 60 s after the start;
   - when two edges fall within 60 s of each other, prefer the one with a supporting cue
     (a start cue within −120/+180 s, an end cue within −180/+60 s), then the one nearest
     the plan;
   - with no edge in the window, fall back to the planned time clipped to coverage, with
     edge kind `schedule`;
   - with no coverage in the window, make no suggestion and count it as `no_coverage`.
5. **Adjacent Program Expectations:**
   - suggestions must not overlap;
   - if two overlap and a changeover lies between them, the earlier ends at the
     changeover start and the later begins at its end;
   - otherwise both keep their times and are marked `overlap`.
6. **Strength**, a categorical result derived from the components, with no numeric score:
   - `strong`: both edges come from changeovers or coverage, and at least one edge has
     silence or cue support;
   - `medium`: both edges come from changeovers or coverage, with no support;
   - `weak`: at least one edge comes from the schedule, or the suggestion is marked
     `overlap`.
7. **Unscheduled activity:** covered, non-changeover spans of at least 120 s that no
   suggestion covers become suggestions with no Program Expectation and strength `weak`,
   for example opening remarks.

**Session Suggestion (advisory, immutable)**

- Fields:
  - run, Event and Stage;
  - Program Expectation ID and revision, or none;
  - suggested start and end (aware, on the recorder clock);
  - components as first-class columns: start and end edge kind; offsets from the plan in
    seconds; silence and cue support per edge; `overlap`; the timing qualification carried
    from the evidence; strength;
  - evidence references: segmentation evidence IDs, timing evidence IDs and revisions,
    transcript revision IDs;
  - policy ID and version.
- Status is **derived**, not stored:
  - `open` while it belongs to the latest run for its Stage and has no decision;
  - `superseded` when a later run exists;
  - otherwise `confirmed` or `rejected`, from its decision.

**Decisions (human, idempotent by command ID with a request digest)**

- **Confirm**, with optional human-adjusted start and end, where start must be before
  end:
  - calls the existing `start_session` with the Program Expectation link, the start, and
    the expectation's title when there is one;
  - then calls `correct_session_boundary` for the end;
  - the Kernel operation IDs are derived deterministically from the confirm command ID
    (UUIDv5), so a retry after a partial failure completes without duplicates;
  - the decision row, which records the resulting Session ID and the times actually used,
    is written last;
  - only an `open` suggestion can be confirmed;
  - a stale expectation revision, or a Session already linked to the same expectation, is
    refused with a typed reason.
- **Reject**, with a bounded reason: records the decision only.
- Nothing is realized automatically. ADR-0026 stays inactive.

**API** (authenticated, bounded, Event-scoped):

- start a run;
- list suggestions for a Stage by status (cursor, limit at most 100);
- read one suggestion with its components;
- confirm;
- reject.

### In scope

1. Migration `0022`:
   - `session_suggestion_run`, `session_suggestion` and `session_suggestion_decision`;
   - immutable by trigger;
   - a guarded reverse that refuses while rows exist.
2. A new `session_suggestions` context in the production layer (not the Kernel):
   - the pure policy and its contracts;
   - the run, confirm and reject services;
   - memory and PostgreSQL repositories.
3. Reads of Program Expectations, assets, timing, segmentation and transcripts through
   existing repositories and ports. Cue matching reuses ED-0092's `match_phrases`.
4. The API routes.
5. Tests: see Test strategy.
6. Documentation:
   - glossary terms Session Suggestion and Suggestion Run;
   - the capability layer;
   - a README for the context.

### Out of scope

- Boundary proposals for realized Sessions (Phase 3).
- The Work Queue item and all UI (Phase 4).
- The corpus harness and accuracy measurement (Phase 5).
- Automatic realization, split or merge.
- Title-card detection; changes to segmentation, timing, transcription or Kernel
  semantics.

### Constraints

- The Kernel is unchanged and must not import the new context. Confirmation goes only
  through the existing human commands.
- The policy is pure and deterministic. Its constants are versioned lineage, and a
  change needs a new policy version.
- No dependency. Offline. Aware timestamps from the injected clock.
- No real-event data in tests.
- Suggestions from unqualified clocks are labelled as such.

### Test strategy

- **Policy, pure, with synthetic timelines:**
  - a clean title-card changeover between two talks;
  - brief freeze breaks merged;
  - short in-talk freezes ignored;
  - a changeover with audio (freeze only);
  - a recording gap as the changeover;
  - schedule drift of up to ±20 min;
  - no edge in the window (schedule fallback, `weak`);
  - no coverage (none, counted);
  - overlap resolution at a shared changeover;
  - unscheduled opening remarks;
  - a cue tie-break;
  - a clock years off (excluded, never placed);
  - an expectation without planned times;
  - withdrawn expectations ignored;
  - determinism (same inputs, identical output).
- **Service and repository:**
  - run idempotency by input digest;
  - skip counts;
  - derived status transitions;
  - confirm calls the Kernel commands with the expected arguments, creates exactly one
    Session, and replays safely after a simulated crash between the Kernel commands and
    the decision write;
  - adjusted times;
  - refusals: not open, stale expectation revision, expectation already realized;
  - reject;
  - immutability.
- **PostgreSQL:** migration forward and reverse, including refusing while rows exist;
  the repository; a transactional replay.
- **API:** shapes, bounds, authentication, typed errors.
- **Import boundary:** the Kernel does not import `session_suggestions`.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.
  The real-corpus accuracy check is Phase 5.

### Acceptance criteria

- [x] A run produces deterministic, lineage-complete suggestions and skip counts from
  schedule, timing, segmentation and optional cues, following policy v1.
- [x] Confirm realizes exactly one Session through the existing human commands,
  idempotently and crash-safely. Reject records a decision. Nothing is automatic.
- [x] Migration `0022` forward and reverse pass; the demo database is backed up before it
  is applied. All checks pass on the host.

### Rollback

Revert the code. Reverse `0022` only while no suggestion rows exist. Sessions realized
through confirmation are ordinary human-realized Sessions and stay.

## Phase 2b: policy v2, joint day alignment (ED-0105)

### Why

- The owner requested an early check before Phase 3:
  [early accuracy check 001](../validation/results/session-suggestions-accuracy-001.md).
  It ran policy v1 on 28 real main-stage talks.
- **v1 meets the target only with an exact schedule.** Median start and end errors are
  15 s and 24 s at zero drift, 47 s and 66 s at ±5 min, and minutes beyond that.
- The cause: long freezes inside talks outnumber real changeovers.
  - in-talk freezes: median 56 s, silent share 0.00;
  - boundary freezes: median 284 s, silent share 0.18.
- A prototype of **joint day alignment** held median errors near 45 s up to ±15 min of
  drift.
- The freeze and gap evidence has a ceiling: only 44 of 56 true edges have any changeover
  within 60 s. Transcript cues are the remaining lever.
- **Owner decision (2026-09-29):** build policy v2 before Phase 3.

### Desired behavior

- **Policy `boundary-suggestion` v2** is deterministic, and its constants are versioned
  lineage. **v1 stays readable** for recorded runs, and new runs use v2. The following are
  unchanged from v1:
  - the timeline placement and clock-plausibility rules (±12 h);
  - the merge gap of 15 s or less;
  - the minimum Session of 60 s;
  - the unscheduled span of at least 120 s;
  - the cue windows;
  - the ±20 min hard edge window.
- **Changeovers:**
  - merged freezes of **at least 60 s**;
  - recording coverage gaps of at least 30 s;
  - the coverage start and end.
- **Changeover strength** is `min(length, 600 s) / 60 × (1 + 2 × silent share)`, where
  the silent share is the fraction of the changeover overlapped by silence intervals.
  - Coverage bounds have strength 30.
  - Coverage gaps have strength `min(length, 600 s) / 60`.
- **Joint alignment:**
  - Each Stage's current, planned Program Expectations are aligned **in planned order**,
    with a monotone dynamic program:
    - talk *i* starts at the end of changeover *j* and ends at the start of changeover
      *k*, which comes after *j* and leaves at least 60 s between them;
    - the next talk starts at the end of changeover *k′* ≥ *k*, so consecutive talks may
      share one changeover.
  - Score: the sum of the strengths of the changeovers used, each counted once, minus the
    sum of |edge − planned time| / **30 s**, plus **1 point per supporting cue** in the
    v1 cue windows.
  - Only edges within ±20 min of the plan are candidates. With none, that edge falls back
    to the planned time, contributes 0, and has edge kind `schedule`.
  - Ties are broken deterministically: earliest edge, then lowest Program Expectation ID.
  - **Clarification (2026-09-29, from the ED-0105 Yellow stop):** the monotone
    constraint applies to changeover, gap and coverage edges.
    - Schedule-fallback edges are exempt, because the plan's inputs can themselves
      overlap: two planned talks whose schedule overlaps, with no candidate edges.
    - When fallbacks leave suggestions overlapping, each keeps its planned times and is
      marked `overlap` (and therefore `weak`), as in v1.
    - No talk is dropped and no run is refused.
    - Otherwise overlaps cannot occur.
  - **Owner continuation decision (2026-09-29, second Yellow stop):** a planned talk
    that cannot yield a valid minimum-duration suggestion is skipped and counted under
    `no_coverage`, exactly as v1 does. A 30-second schedule-only fallback must not raise
    a contract/SQL exception or disappear without a count. Short plans may still use
    evidence to produce a valid interval.
- **Strength (categorical):**
  - `strong`: both edges come from a changeover, gap or coverage, and at least one edge
    has silence support (silent share ≥ 0.3) or cue support;
  - `medium`: both edges come from a changeover, gap or coverage, with no support;
  - `weak`: at least one edge is a schedule fallback, the suggestion is marked
    `overlap`, or it is unscheduled.
- **Unscheduled activity:** as in v1, using v2 changeovers.
- **Evaluation tool:** a pure evaluator that takes suggestions plus anonymous
  ground-truth intervals and reports recall, median and 95th-percentile start and end
  error, and the count within 60 s. It has a CLI that reads a local ground-truth file,
  kept outside the repository, and prints sanitized numbers only. This is pulled forward
  from Phase 5 so v2 can be measured.
- **Migration `0023`** widens the run and suggestion CHECK constraints so version `"1"`
  (exact v1 constants) and version `"2"` (exact v2 constants) are both valid, each exactly
  for its own version. The reverse refuses while v2 rows exist.

### In scope

1. The v2 policy, keeping v1 intact for recorded runs. The service uses v2 for new runs.
2. Migration `0023`, forward and guarded reverse.
3. The evaluator and its CLI, tested only on synthetic fixtures.
4. Tests: see Test strategy.
5. Documentation: the context README, the capability layer, and the glossary if it names
   the policy version.
6. **Owner step:** Accuracy Run 002 on the same corpus with the evaluator, comparing v1
   and v2 at drift 0 and at ±5, ±10 and ±15 min, recorded as a sanitized result.

### Out of scope

- A transcription run over the corpus and cue tuning. These are a follow-up once
  transcripts exist; the v2 cue bonus is present but unmeasured.
- Phases 3–5.
- Any change to Kernel, confirmation or decision semantics.
- UI.

### Constraints

- Pure and deterministic. No dependency. Aware timestamps. No real-event data in tests.
- v1 runs and suggestions stay exact and readable.
- The alignment is bounded: at most 10,000 inputs as in v1. The dynamic program runs per
  Stage and must stay practical, around 50 changeovers per day; document its complexity.

### Test strategy

- **Synthetic timelines:**
  - consecutive talks sharing a title-card changeover;
  - an in-talk 45–60 s slide freeze being ignored;
  - a long silent changeover beating a nearer non-silent freeze;
  - schedule drift of ±15 min still aligning in order;
  - a lunch gap;
  - a missing changeover falling back to the schedule;
  - monotonicity (no overlap);
  - cue bonus effect;
  - determinism and tie-breaking;
  - v1 behaviour unchanged for v1 evaluation.
- **Evaluator:** metrics on hand-computed fixtures.
- **PostgreSQL:** `0023` forward and reverse; v1 and v2 rows each valid only with their own
  constants.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

### Acceptance criteria

- [ ] New runs use v2, v1 records stay valid, and all checks pass on the host.
- [ ] Accuracy Run 002 shows v2, compared with v1:
  - median start and end errors of **35 s or less at zero drift**;
  - **60 s or less at ±5, ±10 and ±15 min**;
  - recall of at least 90%.

  These are the prototype-derived targets. The ADR's 30 s target at every drift remains
  open until transcript cues are measured.

### Rollback

Revert the code. Reverse `0023` only while no v2 rows exist.

## Phase 2c: policy v3, schedule offset (ED-0106)

### Status

- **Approved** (owner, 2026-09-29), including the constants (20 min block break,
  ±60 min grid, 180 s support tolerance, gate of 6 points per talk) and the Accuracy
  Run 003 targets.
- **Execution authority:** Green and implementation-ready.
  - It is authorized by ADR-0034 (a deterministic, versioned policy) and this approved
    section.
  - No Kernel, confirmation or authority semantics change. The migration is additive
    with a guarded reverse, and no dependency is added.
- **Owner decision (2026-09-29, after Accuracy Run 002):** Option B now. Option C is
  planned in Phase 2d.

### Why

- [Accuracy Run 002](../validation/results/session-suggestions-accuracy-002.md) showed
  that v2 meets the target at zero drift. It fails at ±10 and ±15 min, even when a whole
  day is uniformly late.
  - Worst seed under a whole-day shift of ±10 min: recall 0.75, medians 150 s / 143 s.
- **Cause:** v2 charges distance from the **printed** plan. When a Stage runs late, weaker
  in-talk freezes near the printed times outscore the true changeovers.
- Events usually run late as a block: a late start, then a different lateness after
  lunch. That shared offset is the thing v2 does not estimate.
- **Scratch prototype (2026-09-29):**
  - The setup: estimate one offset per schedule block, split at planned breaks of 20 min
    or more; shift the plan by it; run unmodified v2.
  - The corpus, harness and evaluator are the same as in Run 002. The prototype is not
    committed.

  Worst of five seeds, official evaluator. Cells show recall, then median start / end
  error. The **whole-day** model shifts each day by one offset in ±D, plus ±60 s of
  jitter per edge. The **two-part** model uses a different offset after the day's
  largest planned break. The **independent** model is Run 002's drift of ±D per edge.
  The v2 whole-day column is from Run 002 (same drift model, different seeds). The v2
  two-part cells show "—" because v2 was not run on that model. The ground truth caps
  recall at 0.96.

  | Model and drift | v2 (as merged) | v3 prototype, gate 3 | v3 prototype, gate 6 |
  | --- | --- | --- | --- |
  | whole-day ±0 | 0.93, 22 s / 25 s | 0.93, 22 s / 29 s | 0.93, 22 s / 29 s |
  | whole-day ±5 min | 0.89, 47 s / 66 s | 0.93, 28 s / 36 s | 0.93, 29 s / 33 s |
  | whole-day ±10 min | 0.75, 150 s / 143 s | 0.93, 25 s / 30 s | 0.93, 25 s / 30 s |
  | whole-day ±15 min | 0.71, 133 s / 125 s | 0.93, 29 s / 19 s | 0.93, 29 s / 29 s |
  | whole-day ±30 min | — | 0.93, 22 s / 30 s | 0.89, 22 s / 30 s |
  | two-part ±5 min | — | 0.93, 29 s / 24 s | 0.93, 29 s / 24 s |
  | two-part ±10 min | — | 0.96, 25 s / 29 s | 0.93, 25 s / 36 s |
  | two-part ±15 min | — | 0.93, 29 s / 36 s | 0.93, 29 s / 33 s |
  | two-part ±30 min | — | 0.79, 29 s / 33 s | 0.79, 29 s / 33 s |
  | independent 0 | 0.93, 14 s / 18 s | 0.93, 14 s / 18 s | 0.93, 14 s / 18 s |
  | independent ±5 min | 0.89, 30 s / 66 s | 0.75, 37 s / 41 s | 0.89, 37 s / 41 s |
  | independent ±10 min | 0.82, 133 s / 46 s | 0.57, 43 s / 56 s | 0.57, 47 s / 66 s |
  | independent ±15 min | 0.68, 47 s / 184 s | 0.54, 65 s / 181 s | 0.50, 178 s / 66 s |

  - **Where v3 wins:** a block-wide offset recovers the late-running cases. Widening the
    edge window made no difference once the plan was shifted.
  - **Where it loses:** under independent drift of ±10 min or more, the planned
    **durations** are wrong by up to 20–30 min, and one offset per block cannot fit them.
    There, v3 is worse than v2. A producer override of 0 restores v2's behaviour exactly.
  - **Rejected estimator:** choosing the offset that maximizes v2's own alignment score
    reached recall of only 0.82–0.86 on the whole-day and two-part models.

### Desired behavior

- **Policy `boundary-suggestion` v3** is deterministic, and its constants are versioned
  lineage.
  - v1 and v2 stay readable for recorded runs, and new runs use v3.
  - Everything from v2 is unchanged except the steps below. That includes the ±20 min
    edge window, now measured around the **shifted** plan; the prototype found no gain
    from widening it once the plan is shifted.
- **Schedule blocks:**
  - A Stage's current, planned Program Expectations are sorted as in v2.
  - A new block starts wherever the planned gap between one talk's end and the next
    talk's start is **20 min or more** (for example breaks or lunch).
  - Each block gets one offset.
- **Offset for each block, in order of precedence:**
  1. **Producer override**, if one applies to the block (see below). Source `producer`.
  2. **Estimate.** Source `estimated`.
     - **Changeover support:** for a candidate offset δ, sum over the block's planned
       starts and ends, each shifted by δ, of the best nearby changeover:
       `strength × (1 − distance / 180 s)` within ±180 s. Starts use changeover ends,
       and ends use changeover starts. Strength is v2's. Subtract `|δ| / 600 s`.
     - Offsets from **−60 to +60 min** are tried: a 60 s grid, then a 10 s refinement
       around the best.
     - Ties go to the smaller absolute offset, then the earlier one.
     - A **confidence gate** applies: the estimate is used only if it beats offset 0 by
       at least **6 points per talk in the block**. Otherwise the offset is 0 and the source is `none`.
  3. No planned talks, or no changeover evidence: offset 0, source `none`.
- **Alignment:**
  - The v2 joint alignment runs against the shifted plan: each planned start and end,
    plus its block's offset.
  - Distance penalties and the ±20 min window use the shifted times.
- **Suggestion components** (first-class, not metadata):
  - `start_plan_offset_seconds` and `end_plan_offset_seconds` stay relative to the
    **printed** plan, as today. A producer sees "14 min after the printed start".
  - New fields: `schedule_offset_seconds` (the block offset used) and
    `schedule_offset_source` (`producer`, `estimated` or `none`).
  - Strength rules are unchanged from v2. An offset alone never raises strength.
- **Run record:** the run stores one row per block:
  - its ordinal;
  - the first and last planned start of its talks;
  - the talk count;
  - the offset, its source, and the estimate's score margin over offset 0 (a bounded
    number);
  - the override setting version, if one was used.
- **Producer override (Stage schedule offset):**
  - An Event and Stage-scoped, versioned, append-only setting. It follows the
    `event_render_setting` pattern (ED-0099): `command_id` plus `request_digest`
    idempotency, set by, set at, and immutable history.
  - Each version holds 0–20 entries, ordered by time. Each entry has:
    - `effective_from`, an aware timestamp on the planned-time scale, for example
      "from 13:00";
    - `offset_seconds`, an integer from −7,200 to +7,200.
  - A block takes the latest entry whose `effective_from` is at or before the block's
    first planned start. Blocks before the first entry are estimated.
  - A version with no entries clears all overrides.
  - The run's input digest includes the override version, so changing the override and
    rerunning produces a new run. Rerunning without a change produces nothing new.
- **API** (authenticated, bounded, Event-scoped, following the ED-0104 conventions):
  - set a Stage's offset override;
  - read the current override and its history;
  - the run and suggestion responses carry the block offsets and the new components.
- **UI:** none in this phase. Phase 4 gains a Stage summary line, for example "Running
  about 12 min behind the printed schedule (estimated)", with an override control,
  under the owner's scanning rule.

### In scope

1. Policy v3, keeping v1 and v2 intact for recorded runs. The service uses v3 for new
   runs.
2. The Stage schedule offset override: domain, service, repository and API.
3. Migration `0024`, forward and guarded reverse.
4. Tests (see Test strategy).
5. Harness support for Accuracy Run 003:
   - the ED-0105 evaluator is unchanged;
   - drift models live in the external harness, not in the repository.
6. Documentation: the context README, the capability layer, the glossary (schedule
   offset, schedule block), and this plan's completion record.

### Out of scope

- Transcript cues as edges and phrase presets (Phase 2d).
- Phases 3–5, and all UI.
- Any change to Kernel, confirmation or decision semantics.
- Automatic offset learning across Events.

### Constraints

- Pure and deterministic. No dependency. Aware timestamps. No real-event data in tests.
- v1 and v2 runs and suggestions stay exact and readable.
- **Bounded cost:** at most 10,000 inputs as in v1. Estimation evaluates at most
  about 134 offsets per block (121 on the 60 s grid, then 13 in refinement). The
  implementation documents its complexity, and a run on a full day (~50 changeovers,
  ~12 talks) must finish in seconds on the host.
- The override is advisory input to a suggestion policy. It never changes Program
  Expectations, Sessions or any Kernel fact.

### Data and migration (`0024`)

- Run and suggestion CHECK constraints accept version `"3"` with exactly the v3
  constants. v1 and v2 keep their own exact constants.
- `session_suggestion` gains `schedule_offset_seconds` and `schedule_offset_source`.
  They are required for v3 and must be null for v1 and v2, enforced by CHECK.
- A new, immutable `session_suggestion_run_block` table holds the per-block rows above.
- New `stage_schedule_offset_setting` (versioned header) and
  `stage_schedule_offset_entry` (ordered entries) tables, append-only with immutable
  triggers, as in `0020`.
- **Reverse:** refuses while any v3 run or any override setting exists, and otherwise
  drops the additions exactly.
- **Demo database:** back up with `pg_dump` before applying. It is at `0022` today;
  `0023` is pending the owner's approval.

### Test strategy

- **Synthetic timelines:**
  - a whole-day lateness of 25 min is recovered, and every talk aligns to its true
    changeovers;
  - two blocks around a lunch break with different lateness (+5 and +20 min);
  - a producer override replaces the estimate for its blocks only, and an empty version
    clears it;
  - no changeover evidence gives offset 0 with source `none`;
  - a gate case: an ambiguous small gain keeps offset 0;
  - a lateness beyond ±60 min is not estimated, and falls back to v2 behaviour at offset
    0;
  - the grid, refinement and ties are deterministic;
  - the printed-plan offsets and `schedule_offset_seconds` are reported correctly;
  - v1 and v2 behaviour is unchanged for their own versions.
- **Override:**
  - idempotent by command ID;
  - a digest mismatch is refused;
  - history is immutable;
  - entry bounds and ordering are validated;
  - the input digest changes with the override version.
- **PostgreSQL:** `0024` forward and reverse, the guarded reverse, and v1, v2 and v3 rows
  each valid only with their own constants.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

### Acceptance criteria

- [ ] New runs use v3, v1 and v2 records stay valid, and all checks pass on the host.
- [ ] **Accuracy Run 003** (owner step): the same corpus and evaluator as Run 002, five
  seeds, worst seed reported. These targets need owner approval:
  | Scenario (simulated, as in the prototype) | Recall (min) | Median start and end error |
  | --- | --- | --- |
  | Zero drift (independent model) | ≥ 0.90 | ≤ 30 s |
  | Whole-day lateness up to ±15 min | ≥ 0.90 | ≤ 45 s |
  | Whole-day lateness of ±30 min | ≥ 0.85 | ≤ 45 s |
  | Two-part lateness up to ±15 min | ≥ 0.90 | ≤ 45 s |
  | Independent drift of ±5 min | ≥ 0.85 | ≤ 60 s |
  | Independent drift of ±10 and ±15 min | reported, not targeted (known limitation) | — |
- [ ] Setting the true offset as a producer override reproduces the zero-drift results
  within 5 s of median error.

### Rollback

Revert the code. Reverse `0024` only while no v3 runs and no override settings exist.

## Phase 2d: transcript cues as edges, with phrase presets (outline, not implementation-ready)

### Status

- **Draft outline**, recorded 2026-09-29 after the owner's decision to plan Option C
  alongside Option B.
- Not implementation-ready. It needs the owner decisions listed under Open decisions,
  and a detailed section per sub-phase before work starts.
- It follows Phase 2c (ED-0106): v3's measurements decide how much C must add.

### Why

- About 21% of true talk edges have no freeze or recording gap within 30 s (check 001).
  Better selection among changeovers (v2, v3) cannot reach them.
- In the cue analysis on the same corpus, changeover **or** transcript cue evidence lay
  within 60 s of 54 of 56 true edges. Changeovers alone reached 44.
- Today, cues only add a bonus to changeover edges (v2 and v3). They cannot create an edge
  where no changeover exists.
- Phrase lists are hand-typed per Event, 1–200 literal phrases each, through the ED-0092
  API. There are no defaults. A producer has to know which phrases work.

### Owner direction (2026-09-29)

- A phrase list must be modifiable, but start from defaults.
- Preferred: the producer **selects predefined phrase lists, or a combination of them**,
  and can **augment the aggregate with custom phrases**.
- Predefined groupings include:
  - basic introduction and conclusion phrases, with common expected combinations;
  - **studio use:** "action", "cut", "take 1" (or 2, 3 and so on);
  - other use-specific groupings.

### Proposed shape, in two sub-phases

**2d-1: Cue phrase presets and composition (no policy change)**

This is useful on its own: v2 and v3 already use cue lists for support and tie-breaks.

- **Preset catalog:**
  - built-in, versioned, and shipped in code like policy constants;
  - read-only to producers;
  - identified by key and version, so a composed list records exactly what it came
    from.
- **Each preset has:**
  - a key, a version, and a display name;
  - a **use**: general talks, Q&A, studio or production, interview or junket, panel;
  - a **role**: `start` or `end`;
  - its phrases.
- **Numbered templates:** "take {n}" expands at catalog build time into literal phrases,
  both as digits ("take 1") and as words ("take one"), for n = 1–20. The ED-0092 matcher
  stays literal and unchanged, and transcripts can render numbers either way.
- **Composition (the producer's workflow):**
  1. On the Event page, the producer ticks presets, grouped by use.
  2. They see the aggregated phrases grouped by role (start or end), each with a source
     badge (which preset, or custom).
  3. They can remove individual preset phrases, and add custom phrases per role.
  4. Publishing creates new versions of two Event-scoped phrase lists, one for starts and
     one for ends, using the existing ED-0092 phrase-list table.
  5. It also records the composition as first-class provenance: preset keys and
     versions, exclusions, custom phrases, who and when, and command idempotency (the
     ED-0099 setting pattern).
- **Default for suggestion runs:** a run uses the Event's current composed start and end
  lists unless the producer names others. Today a producer must pass list IDs each time.
- **Limits:** the existing 200-phrase cap per list holds. If a composition exceeds it,
  the composition is refused with a clear reason; it is never silently truncated.

**2d-2: cues as edges (policy v4)**

- A new edge kind, `cue`:
  - A start-phrase hit, or a cluster of them (for example an MC's introduction followed
    by the speaker's greeting), becomes a candidate start edge.
  - An end-phrase hit becomes a candidate end edge.
  - This applies only where no changeover lies within a tolerance, so real changeovers
    still win.
- **Strength:** a cue edge is weaker than a real changeover, and a cue-only edge never
  makes a suggestion `strong` on its own.
- **False-hit control:** the cue analysis found 31 end-phrase hits deep inside talks
  ("questions", "thank you"). The candidate rules must use position relative to the
  (offset-corrected) plan and clustering, not single words.
- **Evidence shown to the producer:** the matched phrase and its time, for example
  "Start: cue 'please welcome…' at 14:02:08". This lets a reviewer check a row quickly.
  The phrase text is already in the transcript; nothing new is stored beyond the match
  reference.
- **Degrades cleanly:** without transcripts (local transcription is optional under
  ED-0075), v4 behaves as v3.

### Proposed preset catalog v1 (English; contents for owner review)

> **Superseded by the accepted research-backed catalog (2026-09-29):**
> [Cue phrase catalog v1](../ux/cue-phrase-catalog.md). Accepted by the owner (v1: 11 event profiles, 18
> groups plus 3 regional add-ons; worship and ceremonies deferred), and the roles `start`, `end`, `changeover` and `segment`. It includes measured
> precision on the conference corpus and sources for every other phrase. The table below
> is kept as the originally approved outline.

| Preset | Role | Example phrases |
| --- | --- | --- |
| General introduction (MC) | start | please welcome, welcome to the stage, give it up for, please join me in welcoming, our next speaker, without further ado |
| Speaker opening | start | thank you for having me, my name is, hello everyone, good morning everyone, good afternoon everyone, today I'm going to talk about |
| General conclusion | end | thank you very much, thank you so much, thanks everyone, thank you all, that's all I have, that's it for me |
| Q&A close | end | any questions, time for one more question, last question, we're out of time |
| Applause prompts | end | let's give it up for, a round of applause for, one more time for, please thank |
| Studio: takes and slates | start | action, rolling, speed, take 1–20 (digits and words), scene, mark it |
| Studio: stops | end | cut, that's a wrap, wrap it, reset, back to one, moving on |
| Interview or junket | start | thanks for joining us, welcome to the show, we're here with, joining me today |
| Interview or junket close | end | thanks for talking with us, thanks for coming in, that's all the time we have |
| Panel | start | let me introduce our panelists, please welcome our panel |

Phrases like "give it up for" and "please welcome" sit between two talks: they end one
and start the next. The catalog marks them as changeover phrases, and 2d-2 treats them
as support for **both** edges of a shared changeover.

### Open decisions (owner)

1. **Preset catalog contents and language:** approve or edit the v1 table above. English
   only in v1?
2. **Studio semantics:** in studio use, is a **take** its own Session, a segment inside
   one Session, or ignored for boundaries so that only "action" and "cut" pairs count?
   This touches Session and Segment meaning (Yellow, `AGENTS.md`), so it must be
   answered before 2d-2 treats "take N" as an edge.
3. **Relation to ADR-0035:** a spoken slate ("take 3… action") works like an audio
   marker. Should the studio presets feed ADR-0035's `marked` strength when the Event
   defines them as markers, or stay transcript cues? The default proposal: they stay
   cues; ADR-0035 markers stay non-speech signals.
4. **Scope of use:** should composed lists also be selectable for Editorial derivation
   (ED-0092), or only for boundary cues? The default proposal: boundary cues only in v1.

**Owner decisions (2026-09-29):**

- **Decision 1:** the v1 catalog table above is approved, English only.
- **Decision 3:** studio presets stay transcript cues. ADR-0035 markers stay non-speech
  signals.
- **Decision 4:** composed lists are for boundary cues only in v1.
- **Decision 2 (studio take semantics), decided the same day:** a take signals a
  **segment inside a Session**, not a Session boundary. A series of takes is repeated
  passes at the same content.
  - For 2d-2, "take N", "action" and "cut" must **not** start or end a Session
    suggestion on their own. Session edges still come from changeovers, other cues,
    markers and the schedule.
  - Using takes as Segment evidence (grouping passes within a Session) is a separate,
    later capability, planned with the domain glossary first.
  - 2d-1 may ship the studio presets as cue phrases.

### Dependencies and validation

- 2d-1 has no dependency beyond Phase 2 and can run before or after ED-0106.
- 2d-2 depends on ED-0106 (v3), because cue edges should be positioned against the
  offset-corrected plan.
- **Validation:** an accuracy run of v4 against v3 on the transcribed corpus, with the
  default presets and no tuning to the corpus. A studio-preset check needs a studio
  corpus, which does not exist yet; synthetic tests only until then.

## Phase 2d-1: cue phrase presets and composition (ED-0107 backend, ED-0108 Event page)

### Status

- **Approved** (owner, 2026-09-29), including decisions D1–D3 as proposed.
- **Execution authority:** Green and implementation-ready. ED-0107 first; ED-0108 after
  ED-0107 merges.
- **Content authority:** the accepted
  [Cue phrase catalog v1](../ux/cue-phrase-catalog.md), and the owner decisions recorded
  there on 2026-09-29.

### Why

- Boundary cue lists feed Session suggestions. Today they give cue support and
  tie-breaks in v3; later, cue edges in v4.
- Producers currently have to hand-type literal phrase lists through the ED-0092 API,
  with no defaults, and pass the list IDs on every run.
- The accepted catalog gives research-backed defaults: 11 event profiles, 18 groups and
  3 regional add-ons, with corpus-measured precision.
- Composition turns that into two published cue lists, and records how they were made.

### Verified current behavior

- **Phrase lists (ED-0092):** `editorial_phrase_list` is Event-scoped. Each list has a
  key and a version (`0019`). *(Corrected at completion: the `phrase_list_id` stays stable
  across versions of one key; the draft said a new ID per version.)*
  - Contract: `EditorialPhraseList` in `contexts/editorial/derivation_contracts.py`,
    which allows 1–200 phrases of 1–100 characters and rejects normalized duplicates.
  - Publishing is a human, idempotent command (`derivation_service.py`,
    `POST /editorial/events/{event_id}/phrase-lists`).
- **Matching:** literal whole-token sequences within one transcript segment
  (`contexts/editorial/derivation.py::match_phrases`).
- **Suggestion runs** accept optional `start_cue_list` and `end_cue_list` references
  (`api/v1/session_suggestions.py`, `RunBody`). With none given, no cues are used. The
  lists are part of the run input digest and lineage (ED-0104).
- **Event page:** it has one producer settings section, render quality
  (`frontend/app/event/page.tsx`, `components/event-render-quality.tsx`, ED-0099/0100).
  It follows the pattern of per-capability same-origin proxy routes with allowlists
  (`capability-proxy.server.ts`, D1 in `producer-outputs-ui.md`).
- **Session suggestions** have no frontend route or proxy capability yet (Phase 4).

### Desired behavior

**Catalog (in code, read-only)**

- The **Boundary cue catalog** is `boundary-cue-catalog` version `1`. It is a pure,
  immutable Python constant in `contexts/production/session_suggestions/`.
- **Content:** exactly the non-deferred v1 content of the accepted catalog document:
  - 11 profiles, 18 groups (incl. `studio.setups`, added from the ED-0107 review) and
    3 regional add-ons. Worship and ceremonies are **not**
    shipped.
  - Each group has a key, a version (`1`), a name, a category and phrases.
  - Each phrase has its literal text, a role (`start`, `end`, `changeover` or
    `segment`), a default flag (`true`, or `false` for opt-in ⚠ phrases) and its evidence
    label from the document.
  - Each profile has a key, a name and its pre-ticked group keys.
- **Templates:** `take {n}` and `scene {n}` expand at build time for n = 1–20, both as
  digits and as words ("take 3", "take three").
- **Validation at import:**
  - group and profile keys are unique;
  - every phrase passes the `EditorialPhraseList` phrase rules;
  - there are no normalized duplicates within a group;
  - every profile refers only to existing groups.
- **Catalog digest:** SHA-256 over a canonical serialization. It is recorded in every
  composition as provenance.
- The *Excluded from v1* phrases are not in the catalog. Producers can add them as custom
  phrases.

**Composition (human command, Event-scoped, versioned)**

- **Inputs:**
  - the catalog version;
  - an optional profile key, for provenance only;
  - the ticked group keys;
  - `include` choices, which are opt-in phrases (group and phrase) to add;
  - `exclude` choices, which are default phrases (group and phrase) to remove;
  - custom phrases, each with a role;
  - the actor, and a command ID.
- **Deterministic result:**
  1. Take each ticked group's default phrases, plus included opt-ins, minus exclusions,
     plus custom phrases.
  2. Merge phrases that normalize to the same tokens. A merged phrase takes the **union
     of its roles**: a phrase that is `start` in one group and `end` in another behaves
     as `changeover`.
  3. **Start cue list** = `start` and `changeover` phrases. **End cue list** = `end` and
     `changeover` phrases. Each list is ordered by first appearance in catalog order,
     then custom order.
  4. `segment` phrases are stored with the composition and are **not** published (owner
     decision). A custom phrase may not use the `segment` role in v1.
- **Validation:**
  - Every referenced group, and every include or exclude choice, must exist in the
    stated catalog version, and a choice must match that phrase's default flag.
  - Custom phrases follow the phrase rules.
  - Each published list must have 1–200 phrases. Otherwise the command is refused with
    `cue_list_empty` or `cue_list_too_large` and a count. Nothing is ever truncated.
- **Publishing:** in one transaction, all or nothing:
  - a new version of each of two ED-0092 phrase lists, with the reserved keys
    `boundary-cues-start` and `boundary-cues-end`;
  - one composition record that references both, with first-class provenance: catalog
    ID, version and digest; profile; groups and their versions; include and exclude
    choices; custom phrases with roles; segment phrases with their sources; composed by;
    composed at.
- **Idempotency:** `command_id` plus `request_digest`, as for the ED-0099 settings. The
  same command replays; a different body with the same command ID is refused.
- **History:** append-only and immutable. The latest version is the Event's **current
  composition**.

**Suggestion runs use the current composition by default**

- When a run names **neither** cue list and the Event has a current composition, the run
  uses that composition's two published lists.
- When the run names any list, the named lists are used exactly as today, with no
  mixing.
- The lists used are recorded in the run, and are already part of its input digest.

**API** (authenticated, bounded, following ED-0104 conventions)

- read the catalog;
- create a composition;
- read the current composition and its history;
- run responses already carry the cue-list references they used.

**Event page (ED-0108)**

- A new **Boundary cue phrases** section, following the owner's scanning rule and the
  render-quality pattern (ED-0099/0100).
- **Summary first,** for example: "Conference stage · 4 groups · 38 start / 31 end
  phrases · composed Tue 14:05". Or "Not set up: suggestions run without cues".
- **Editing:**
  - pick a profile, which pre-ticks its groups;
  - groups are shown by category with their phrase counts;
  - an aggregate view by role, where each phrase shows a source badge and an evidence
    badge;
  - remove a phrase, add an opt-in phrase (marked ⚠), or add a custom phrase with a
    role;
  - live counts against the 200 limit;
  - publish with a confirmation.
- **Details (collapsed):** version history, the composing actor and ID, and the catalog
  version.
- **Proxy:** a new `session-suggestions` proxy capability, with an allowlist of the
  catalog and composition routes only.
- **Owner UX checkpoint**, with screenshots, before merge.

### Decisions (owner approval of this section approves the proposed defaults)

- **D1. Reserved list keys:** the ED-0092 publish command refuses the keys
  `boundary-cues-start` and `boundary-cues-end`, so manual publishes cannot mix into
  composed lists.
  - This is a small, additive restriction on an existing API. No existing data uses
    these keys: the migration checks, and refuses if any rows exist.
  - Alternative: allow manual publishes to those keys. Rejected, because it breaks
    provenance.
- **D2. Run default:** use the composition only when a run names no list (proposed).
  - Alternative: fill in each missing list separately. Rejected as confusing.
- **D3. Delivery:** two directives. ED-0107 is the backend: catalog, composition,
  migration `0025`, API and run default. ED-0108 is the Event page, with the UX
  checkpoint.

### In scope

- **ED-0107:**
  1. The catalog constant, its validation and digest, plus the template expansion.
  2. The composition domain, service and repository, with migration `0025`: composition
     header and child tables, immutable triggers, the reserved-key check, and a guarded
     reverse.
  3. The composition API, and the catalog read API.
  4. The reserved-key refusal in the ED-0092 publish command.
  5. The run default.
  6. Tests.
  7. Docs: the context README, the capability layer, and glossary entries for **boundary
     cue catalog**, **cue phrase group**, **event profile** and **boundary cue
     composition**, including the roles.
- **ED-0108:**
  1. The Event page section.
  2. The proxy capability and allowlist.
  3. Frontend tests.
  4. The UX checkpoint record in `docs/ux/operator-feedback.md`.

### Out of scope

- Cue edges (policy v4, Phase 2d-2).
- Segment use of `segment` phrases.
- Editorial derivation using composed lists (boundary use only, by owner decision).
- Deferred groups: worship and ceremonies.
- Languages other than English.
- Automatic re-runs when a composition changes.

### Constraints

- No dependency. Pure, deterministic composition. Aware timestamps.
- No real-event data in tests. The catalog phrases are generic language, not event
  content.
- Existing ED-0092 phrase lists, derivation runs and suggestion runs stay valid and
  readable. Explicitly named cue lists behave exactly as today.
- White-label.
- The UI never exposes evidence counts as guarantees. The evidence badge says
  "measured on one conference" or "from published scripts".

### Data and migration (`0025`)

- New tables:
  - `boundary_cue_composition`: Event, version, command ID and digest, catalog ID,
    version and digest, profile key, the start and end phrase-list ID and version,
    composed by and at;
  - child tables for groups, choices, custom phrases and segment phrases.
- All of them are append-only, with immutable triggers (the `0020` pattern).
- The forward migration **refuses** if any `editorial_phrase_list` row already uses a
  reserved key (D1).
- The reverse refuses while any composition exists, and otherwise drops exactly the
  additions.
- **Demo database:** back up with `pg_dump` before applying. The owner must authorize
  explicitly.

### Test strategy

- **Catalog:**
  - the exact group and profile keys, and the phrase counts per group, match the
    accepted document;
  - deferred groups are absent;
  - template expansion gives 40 `take` and 40 `scene` phrases;
  - the import validation rejects each malformed case;
  - the digest is stable.
- **Composition:**
  - profile defaults;
  - include and exclude;
  - custom phrases;
  - a role union that makes a phrase `changeover`;
  - normalized dedupe across groups;
  - segment phrases stored but not published;
  - the 200 limit and the empty-list refusal;
  - unknown group or phrase choices refused;
  - deterministic ordering;
  - idempotent replay, and a digest conflict;
  - atomicity: a failure after the first list insert leaves nothing.
- **Runs:**
  - no named lists plus a current composition uses the composed lists;
  - named lists are unchanged;
  - no composition means no cues, as today;
  - the input digest changes with the composition.
- **ED-0092:** the reserved keys are refused, and other keys are unchanged.
- **PostgreSQL:** `0025` forward and reverse, both guards, and rolled-back fixtures.
- **Frontend (ED-0108):**
  - rendering from fixtures;
  - selection and aggregate logic;
  - limit counters;
  - the proxy allowlist;
  - `npm run test`, `build`, `lint` and `typecheck`.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

### Acceptance criteria

- [ ] ED-0107: the catalog matches the accepted document. Composition, API, run default,
  reserved keys and `0025` are implemented, and all checks pass on the host.
- [ ] ED-0108: the Event page section works end to end against a local backend. The
  owner UX checkpoint passes.
- [ ] **Owner step, Cue Run 001:**
  - Compose the *Conference stage* profile. Run the Run 003 harness for v3 with the
    composed lists, against v3 with the untuned Run 002 lists.
  - Report recall and median errors for the whole-day and two-part models.
  - The composed lists must be **no worse** than the untuned lists on any reported
    target.

### Rollback

- Revert the code.
- Reverse `0025` only while no composition exists.
- Published phrase-list versions are ordinary ED-0092 rows and stay readable.


### Completion record (ED-0107)

- **Implemented revision:** `ab2f5a1`, merged in PR #155 (`main` `2788e6c`). Codex
  implemented it and the owner committed it.
- **Changed files:**
  - `cue_catalog.py`, `cue_composition.py` and `cue_service.py` (new);
  - the session-suggestion API, service, repositories and in-memory store;
  - the ED-0092 publish (reserved keys);
  - `boundary_cue_repository.py` (new) and migration `0025` (forward and reverse);
  - the context README, capability layer and glossary;
  - the catalog document, amended by the owner;
  - new tests `test_boundary_cue_{catalog,composition,api,postgres}.py`.
- **Changed existing assertions:** five, all pre-authorized: `0025` added to the migration
  lists in three test files.
- **Review:** `directive-reviewer` returned ESCALATE, then APPROVE.
  - The escalation: the *Film or studio set* profile had no `start` phrase, so it could
    never publish.
  - Owner decision: add `studio.setups` ("picture's up"). The catalog is now 18 groups.
  - Codex also added a test and a README note that an exclusion applies per source group,
    and mapped editorial publish conflicts to 409.
  - A mechanical comparison of the catalog against the document found zero mismatches.
- **Tests (host):** full backend suite **2,966 passed, 0 failed, 2 skipped**. Ruff and
  Pyright clean. CI green.
- **Demo database:** backed up (`stageflow_demo-pre-ed0107-0025-*`) and migrated to
  `0025` with the owner's approval.
- **Cue Run 001 (2026-09-29):**
  [result](../validation/results/boundary-cue-run-001.md).
  - Every Run 003 target is met.
  - Cell by cell against the untuned lists: better or equal in 12 of 15 cells. It is
    worse in 3, by at most 3.3 s, or one talk of recall in a cell that is not a target.
- **Status:** Completed.
- **Follow-ups:**
  - ED-0108 (the Event page section). Its "remove phrase" must exclude the phrase from
    every source group.
  - Optional non-blocking review notes:
    - the catalog GET does not check that the Event exists;
    - the reserved-key check is case-sensitive, which is harmless because keys are
      stored case-sensitively.


### Completion record (ED-0108)

- **Implemented revision:** `a73499c`, merged in PR #157 (`main` `7ce8267`). Codex
  implemented it and the owner committed it.
- **Changed files:**
  - the Event page (`frontend/app/event/page.tsx`) and the new
    `event-boundary-cues.tsx` component;
  - the `boundary-cues` helpers, API client and fixtures;
  - the new `session-suggestions` proxy route and its allowlist entries;
  - command audit;
  - `ui-labels.ts` and styles;
  - tests;
  - the glossary "UI wording" section;
  - the UX checkpoint record in `docs/ux/operator-feedback.md`.
- **Changed existing assertions:**
  - the proxy and audit test matrices were extended;
  - two assertions in the new cue tests changed at the owner's UX request: removed
    phrases move to Removed and persist across group ticks.
- **Review:** `directive-reviewer` returned APPROVE, and APPROVE again after the UX
  changes.
- **Owner UX checkpoints:**
  - **First:** six changes requested and implemented: ticked groups first with "More
    groups"; grouped one-line phrases with exception-only badges; Removed with Add back;
    ⚠ from evidence; "Custom (based on …)"; removals persist across group ticks.
  - **Second:** approved.
- **Tests (host):** frontend `npm run test` **304 passed, 0 failed**; lint, typecheck and
  build clean. Full backend suite **2,966 passed, 0 failed, 2 skipped**. CI green.
- **Live check:** against the demo database, the *Conference stage* composition was
  published through the UI as version 1. It had one removal and one custom phrase, and
  the page's 32 start / 32 end counts matched the published lists.
- **Status:** Completed. Phase 2d-1 (ED-0107 and ED-0108) is complete.

## Phase 4: Producer surfaces for Session suggestions (ED-0109 backend, ED-0110 Stage page)

### Status

- **Approved** (owner, 2026-09-29), including decisions D1–D6 as recommended.
- **Execution authority:** Green and implementation-ready. ED-0109 first; ED-0110 after
  ED-0109 merges.
- **Order (owner, 2026-09-29):** Phase 4 comes first, then Phase 3 (boundary proposals for
  realized Sessions, on Session Detail), then Phase 5 (validation harness and
  qualification run). Phases 3 and 5 each get a detailed section after this phase.

### Why

- Everything built in Phases 1–2d is reachable only through the API: suggestion runs,
  policy v3 schedule offsets, and cue compositions.
- A producer cannot yet see suggested presentations, confirm or reject them, or see and
  correct how late a Stage is running.
- ADR-0034 places suggestions in the Work Queue ("confirm presentation") and in the
  Producer surfaces.

### Verified current behavior

- **Suggestion API** (`backend/app/api/v1/session_suggestions.py`, prefix
  `/session-suggestions/events/{event_id}`):
  - start a run;
  - list suggestions for a Stage by status;
  - read one suggestion;
  - confirm, optionally with adjusted start and end; reject with a bounded reason;
  - set, read and list the history of a Stage's schedule offset;
  - the cue catalog and composition routes.
  - There is **no read of the latest run**: its blocks, offsets, skips and cue lists.
- **Work Queue** (`contexts/production/work_queue.py`): `ProducerWorkQueueService` merges
  Kernel items with Assembly approval items.
  - Priorities: association conflict 1, association unresolved 2, package correction 3,
    package ready 4, Assembly approval pending 5 (ED-0101).
  - The item types are `ProducerWorkDecisionType` and `ProducerWorkSubjectKind` in the
    Kernel contracts.
  - The Kernel does not import the Assembly context; an import-boundary test checks this.
  - `GET /api/v1/events/{event_id}/work-queue` exists.
  - **There is no Work Queue page in the frontend.** Its UX specification
    (`docs/ux/producer-sessions-work-queue.md`) is still Draft v0.1.
- **Frontend:**
  - The Stage page (`frontend/app/stages/[stageKey]/page.tsx`,
    `StageOperationalView`) shows operation and authority status for one Stage.
  - Mission Control (`frontend/app/page.tsx`) shows the Event overview and Attention.
  - The `session-suggestions` proxy capability currently allows only the catalog and
    composition routes (ED-0108).
- **Human authority:** confirm calls the existing Kernel `start_session` and
  `correct_session_boundary` commands, with IDs derived deterministically from the
  command (ED-0104). Nothing is realized automatically.

### Decisions (owner approval of this section approves the recommended defaults)

- **D1. Where suggestions are reviewed:** a **Suggested presentations** panel on the
  **Stage page** (recommended). Suggestions are per Stage and ordered by time, and the
  Stage page is where a producer already looks at one stage.
  - Alternative: build the Work Queue page now. Rejected for this phase, because its UX
    specification is still Draft and would need its own decisions.
- **D2. Work Queue item:** a new additive item, `presentation_confirmation_pending`,
  with subject kind `stage_suggestions`.
  - There is **one item per Stage** that has open suggestions in its latest run. Its
    reason codes carry the count of open and weak suggestions, and its action reference
    points to the Stage.
  - **Priority 6,** after Assembly approvals.
  - It is visible through the Work Queue API now, and on a future Work Queue page.
  - Alternative: one item per suggestion. Rejected, because a conference day would add
    about 30 items and flood the queue.
- **D3. Mission Control:** one summary line per Stage with open suggestions, such as
  "Main stage: 9 suggested presentations to confirm (2 weak)", linking to the Stage page.
  Nothing appears when there are none.
- **D4. Confirming:** one suggestion at a time, with an optional adjustment of start and
  end in local time and a confirmation step. **No batch confirm in v1**, so every Session
  stays a deliberate human decision. Batch confirm can follow once you've used this.
- **D5. Schedule offset on the Stage panel:**
  - The latest run's block offsets are shown as a summary, for example "Running about 12
    min behind the printed schedule (estimated)", or per block when blocks differ.
  - An override editor sets or clears entries, using the existing ED-0106 API.
  - Changing the override does not re-run anything. The panel then offers "Suggest
    again".
- **D6. Data for the UX checkpoint:** a local seeding script, not committed, creates
  anonymous Program Expectations ("Talk 1…n") on the demo database.
  - It runs segmentation and timing on local media, or uses the ground-truth corpus's
    cached segmentation, locally only. Screenshots show only anonymous titles.
  - Nothing real-event is committed, as for the earlier runs.

### Desired behavior

**ED-0109 (backend, additive)**

- **Latest run read:** `GET .../stages/{stage_id}/runs/latest` returns the latest run's:
  - ID;
  - created at, and the actor;
  - policy version;
  - input digest;
  - skips;
  - blocks, with offset, source and margin;
  - override version;
  - cue-list references.

  It returns 404 when there is no run.
- **Work Queue item** (D2): a Session Suggestions read port lists Stages with open
  suggestions in their latest run.
  - `ProducerWorkQueueService` merges them with the other items under the unchanged
    keyset cursor, as ED-0101 did.
  - The enum values are added to the Kernel contracts.
  - **The Kernel does not import the Session Suggestions context,** and the import-boundary
    test is extended.
  - The item appears as soon as any open suggestion exists, and disappears when none are
    open or a newer run supersedes them. Its `updated_at` is the latest run's time.
- The Work Queue API filter and serialization accept the new values.

**ED-0110 (frontend)**

- **Stage page, Suggested presentations panel.** Summary first, following the owner's
  scanning rule:
  - **Summary line:** "9 suggested · 2 weak · last suggested 14:05 · running about 12 min
    behind (estimated)". Or "No suggestions yet". With no planned talks: "Add the
    schedule first".
  - **Actions:** **Suggest presentations**, which starts a run. It uses the Event's cue
    composition by default, and shows the run's skips as readable exceptions when present.
  - **List:** open suggestions in time order, one row each. Each row shows the planned
    talk title (or "Unscheduled activity"), the suggested start and end in local time,
    the length, and the difference from the printed schedule, for example "+12 min".
    - Only exceptions get a badge: weak, overlap, schedule fallback, estimated offset,
      producer offset. A strength explanation is under the row's Details.
    - Evidence goes under Details: the edge kinds, silence and cue support, and the
      internal IDs.
  - **Confirm** opens a small confirmation. It shows the times and allows optional
    adjustments, with validation that start is before end. Refusals are shown as readable
    messages: a stale schedule revision, a Session already linked, a Kernel conflict.
  - **Reject** takes a bounded reason picker.
  - Confirmed and rejected suggestions collapse into "Decided · N". Superseded ones
    are hidden, with a count.
  - **Schedule offset** (D5): the summary and an override editor, with entries of "from
    <local time>, ±N min" and clear.
- **Mission Control:** the per-Stage summary line (D3).
- **Proxy:** the `session-suggestions` allowlist is extended with exactly these routes:
  - runs (POST) and runs/latest (GET);
  - the suggestion list and read;
  - confirm and reject;
  - schedule offset set, current and history;
  - the Work Queue read, if Mission Control needs it.

  The POSTs are audited, with no free text in logs, and the same authorization rule as
  the other sections applies.
- **Labels** go in `ui-labels.ts` and the glossary "UI wording" section. For example,
  weak → "Needs a closer look", and schedule fallback → "From the schedule only".
- **Owner UX checkpoint** with screenshots before merge (D6 data).

### In scope

- **ED-0109:**
  1. The latest-run read.
  2. The Work Queue item and the read port.
  3. The import-boundary test.
  4. API filter and serialization updates.
  5. Tests.
  6. Docs: the context README, the capability layer, and the glossary (Work Queue item
     type).
- **ED-0110:**
  1. The Stage panel.
  2. The Mission Control line.
  3. The proxy allowlist and audit.
  4. Labels.
  5. Frontend tests.
  6. The UX checkpoint record.

### Out of scope

- The Work Queue page.
- Batch confirm.
- Boundary proposals for realized Sessions and their Session Detail surface (Phase 3).
- The validation harness (Phase 5).
- Automatic runs.
- Cue edges (Phase 2d-2).
- The override-splits-blocks follow-up.
- ADR-0035 markers.

### Constraints

- No migration is expected for ED-0109. If one proves necessary, stop and report.
- No dependency. No change to Kernel semantics or authority.
- Confirm keeps using the existing human commands.
- Existing Work Queue items, their order and the cursor behave as before.
- White-label. No real-event data in tests or commits.

### Test strategy

- **ED-0109:**
  - The latest run is read, and 404 is returned when none exists.
  - The Work Queue item appears with open suggestions, and its counts are right.
  - It disappears when all are decided or a newer run supersedes them.
  - Priority and sort place it after Assembly approvals.
  - The cursor works across the merged types.
  - The import boundary holds.
  - The API filter accepts the new type.
  - PostgreSQL read tests use rolled-back fixtures.
- **ED-0110:**
  - rendering from fixtures: no suggestions, open, weak, decided, skips, and offsets;
  - confirm with and without adjustment, validation, and refusal mapping;
  - reject;
  - "Suggest presentations" and its error states;
  - the offset editor;
  - the Mission Control line;
  - the proxy allowlist: allowed and refused, including the absence of unrelated
    routes;
  - audit;
  - `npm run test`, `lint`, `typecheck` and `build`.
- **Quality gate:** the full host backend suite, Ruff, Pyright, and `git diff --check`.

### Acceptance criteria

- [ ] ED-0109: the latest-run read and the Work Queue item are implemented as above, and
  all checks pass on the host.
- [ ] ED-0110, end to end against the demo database with the D6 data, as a producer:
  - see the Stage's suggestions and schedule offset;
  - set an override and suggest again;
  - confirm one suggestion, which creates a Session visible in Sessions;
  - adjust and confirm another;
  - reject one;
  - see the Mission Control line and the Work Queue item update accordingly.
- [ ] The owner UX checkpoint passes.

### Rollback

Revert the code. ED-0109 adds no schema. Sessions created by confirmations are ordinary
Kernel Sessions, and are corrected through the existing commands.


### Completion record (ED-0109)

- **Implemented revision:** merged in PR #160 (`main` `c715c6b`). Codex implemented it
  and the owner committed it.
- **Changed files:**
  - the latest-run read: API, service, and the PostgreSQL and in-memory repositories;
  - the Session Suggestions Work Queue read port (`session_suggestions/work_queue.py`);
  - the three-source merge in `production/work_queue.py`;
  - the Kernel contract enum values;
  - the Work Queue API response literals;
  - bootstrap wiring;
  - tests: `test_session_suggestions_surfaces{,_postgres}.py`, plus the import-boundary
    assertion;
  - the context README, capability layer and glossary.
- **Plan correction:** this section assumed that the Work Queue API already had a
  decision-type filter. It had none.
  - Codex added one. The reviewer found it out of scope, with unbounded cost for rare
    item types, so it was **removed**.
  - No filter exists. If a later phase needs one, plan it then (for example, a
    priority-window push-down).
- **Review:** `directive-reviewer` returned FIX-FIRST (the filter), then APPROVE.
- **Tests (host):** full backend suite **2,979 passed, 0 failed, 2 skipped**. Ruff and
  Pyright clean. CI green. No migration.
- **Status:** Completed.

### Completion record (ED-0110)

- **Implemented revision:** merged in PR #161 (`main` `e9b224e`).
- **Changed files:**
  - the Stage page Suggested presentations panel (`stage-suggestions.tsx`);
  - the Mission Control strip (`suggestion-queue-lines.tsx`);
  - the session-suggestions helpers, API client and fixtures;
  - the proxy allowlist extension, plus a read-only `producer` capability for the Work
    Queue GET;
  - audit, labels and styles;
  - the frontend README capability table;
  - tests;
  - the glossary "UI wording" section;
  - the UX checkpoint record.
- **Review:**
  - `directive-reviewer` returned FIX-FIRST: "Add the schedule first" was missing for
    Stages with no schedule.
  - The owner's live-check fixes followed: panel placement, same-day ranges, compact
    rows, the Mission Control strip, and plurals.
  - The reviewer then returned APPROVE.
- **Owner UX checkpoint:** approved with one change: the producer-offset badge appears
  only when a row differs from the summary.
- **Live check (D6):** two locally seeded synthetic review Events were processed through
  real discovery, timing inspection and segmentation (24 blocks on the second). Suggest,
  confirm, adjust-and-confirm, reject, offset override and suggest again were exercised
  end to end. The lateness estimate matched the true 8 min on the realistic day.
- **Tests (host):** frontend `npm run test` **346 passed, 0 failed**; lint, typecheck and
  build clean. Full backend suite **2,979 passed, 0 failed, 2 skipped**. CI green.
- **Findings recorded** (in `docs/ux/operator-feedback.md`):
  - re-suggesting talks that already have a Session: see ED-0111 below;
  - the recording start outscoring short changeovers, which can alias the offset
    estimate on short, evenly spaced talks: a policy follow-up candidate;
  - recordings not re-matched after a confirm: this predates ED-0110 and is out of
    scope.
- **Status:** Completed. **Phase 4 is complete.**

### Follow-up: exclude talks that already have a Session from new runs (ED-0111)

- **Status:** Proposed (2026-09-29), from the ED-0110 UX checkpoint.
  - It becomes Green and implementation-ready on owner approval of this section.
- **Owner decisions (2026-09-29):**
  - a talk that already has a Session is not suggested again;
  - it is counted and shown as "already a Session";
  - rejected talks **may** be suggested again on a new run.
- **Problem:**
  - Every run suggests every current, planned Program Expectation.
  - After a producer confirms Talk 1, "Suggest again" re-suggests it as open, and Mission
    Control counts it again.
  - Confirming it again is safely refused (`expectation_already_realized` in the
    service), but the list and counts mislead.
- **Design, with no policy change:**
  - Realized expectations **stay in the policy input.** They still anchor the joint
    alignment of their neighbours, and their spans are not re-suggested as unscheduled
    activity.
  - The run then **stores no suggestion** for an expectation that has a Session linked
    to it (`Session.program_expectation_id`), and counts it in a new run skip,
    `already_realized`.
  - The set of realized expectation IDs becomes part of the run's input digest, so
    confirming a talk and suggesting again creates a new run.
  - This is a service-level filter over the unchanged v3 result. v1–v3 policy constants
    and stored runs are unaffected.
- **Migration `0026` (additive):**
  - `session_suggestion_run.already_realized` is added as `integer NOT NULL DEFAULT 0
    CHECK (already_realized >= 0)`, so existing runs read as 0.
  - The reverse drops the column.
- **API and UI:**
  - The run and latest-run responses carry `already_realized`.
  - The Stage panel summary adds "· N already a Session" (singular and plural) when it
    is non-zero.
  - The Work Queue counts are unchanged in shape; they now exclude realized talks,
    because no suggestion is stored for them.
- **Out of scope:**
  - hiding rejected talks;
  - re-matching recordings to Sessions after a confirm;
  - policy tuning for the recording-start boundary.
- **Tests:**
  - confirm Talk 1, then run again: no suggestion for Talk 1, `already_realized = 1`, and
    Talk 2's alignment is unchanged;
  - no unscheduled suggestion over Talk 1's span;
  - a rejected talk is suggested again;
  - the digest changes after a confirm;
  - `0026` forward and reverse, and old runs read as 0;
  - the frontend summary wording;
  - the full host backend and frontend suites.
- **Acceptance:** the tests above pass on the host, plus a live re-check on the review
  Event: after confirm → suggest again, the confirmed talks show as "already a Session",
  not as open suggestions.
- **Rollback:** revert the code and reverse `0026`.

## Ground-truth corpus handling (all phases)

- Real-event media, the decoded ground truth and scripts stay outside the repository:
  `C:\StageFlowDemo\ground-truth\`.
- Committed results use only anonymous identifiers (`talk 1`, `stage A`), durations and
  error statistics.

## Completion record

- **Phase 1 (ED-0103), implemented revision:** branch `codex/ed-0103-media-segmentation`.
  Codex implemented it and the owner committed it.
- **Changed files:**
  - migration `0021` (a `media_segmentation` operation kind; three kind-membership
    constraints widened, with exact requirements kept for existing kinds; evidence and
    interval tables; a guarded reverse);
  - the `media_segmentation_evidence` context;
  - the FFmpeg segmentation adapter (shares the render identity check through
    `identify_ffmpeg`);
  - the CPU worker and the `[local_media_segmentation]` config;
  - default-off bounded enqueue and backfill;
  - the bounded API;
  - the PostgreSQL repository;
  - tests and documentation.
  - No dependency.
- **Changed existing assertions:** three migration-order lists, which were pre-authorized.
- **Review:** `directive-reviewer` returned FIX-FIRST, then APPROVE.
  - F1: an end-of-file silence end overshooting the measured duration made the asset fail
    permanently. The owner fixed it: only an *end* offset up to 1 s past the duration is
    clamped, and starts stay strict.
  - F2: tests now use the real FFmpeg 8.1 line shapes.
- **Tests (host):** full backend suite **2,765 passed, 0 failed, 2 skipped**, on a freshly
  reset test database. Earlier parallel sandbox runs had left the shared test schema
  inconsistent. Ruff and Pyright clean.
- **Owner real-FFmpeg run:**
  [Segmentation Run 001](../validation/results/media-segmentation-001.md).
- **Remaining work:**
  - migrate the demo database to `0021` after merge, backing it up first;
  - Phase 2 (the suggestions core and policy) needs its detailed section.
  - Non-blocking review notes for later:
    - the fixed 3600 s timeout does not scale with asset length;
    - `N/A` `out_time_us` handling;
    - only the first audio track is analysed;
    - results are tied to the current profile version.
- **Phase 2 (ED-0104), implemented revision:** branch `codex/ed-0104-session-suggestions`.
  Codex implemented it and the owner committed it.
  - **Changed files:**
    - migration `0022` (`session_suggestion_run`, `session_suggestion`,
      `session_suggestion_decision`; immutable; guarded reverse; a non-unique
      `(stage_id, input_digest)` index);
    - the production-layer `session_suggestions` context (a pure policy
      `boundary-suggestion` v1, the service, memory and PostgreSQL repositories, a README);
    - the API routes and the router;
    - four new test files;
    - the glossary and the capability layer.
    - The Kernel files are unchanged. No dependency, frontend or configuration change.
  - **Approved deviation:** confirmation calls the existing Kernel `start_session` and
    `correct_session_boundary` (UUIDv5 operation IDs) inside the suggestion transaction.
    It borrows the connection through `_BoundKernelRepository`, so both Kernel writes and
    the decision commit or roll back together. This is stricter than the plan's
    "decision last" replay: a half-realized Session is never visible. A guard test fails
    if the Kernel adapter ever commits itself or connects outside `_connect`.
  - **Review:** `directive-reviewer` returned FIX-FIRST, then APPROVE.
    - F1: returning to earlier inputs (A→B→A) replayed a superseded run. Now a prior run is
      reused only while it is the Stage's latest.
    - F2: suggestion reads and runs took Stage and Program Expectation row locks that
      would block live Kernel commands. Now only confirm and reject take them, and a
      lock-timeout test proves a Kernel start on another Stage is not blocked.
    - Also: cue-version bounds, a non-vacuous import boundary, and refusal of an adjusted
      end at or before the start.
  - **Changed existing assertions:**
    - three migration-order lists (pre-authorized);
    - the run-replay assertion changed for F1 (owner-authorized).
  - **Tests (host):** full backend suite **2,821 passed, 0 failed, 2 skipped**, on a reset
    test database. The owner approved resetting only the test schema, after an earlier
    version of the lock test left three immutable rows that blocked the reversal tests.
    Ruff and Pyright clean.
  - **Remaining work:** back up the demo database and migrate it to `0022` after merge.
    Phase 3 (boundary proposals), Phase 4 (surfaces) and Phase 5 (corpus validation) each
    need their detailed section.
- **Phase 2b (ED-0105), implemented revision:** branch `codex/ed-0105-policy-v2`. Codex
  implemented it and the owner committed it, with the review fixes below.
  - **Changed files:**
    - `policy_v2.py`, a joint dynamic program with O(T·C³) worst case, bounded in practice
      by the ±20 min candidate window;
    - `evaluation.py` and `evaluate_cli.py`, which produce sanitized metrics only;
    - contracts, serialization, the service (new runs use v2) and the PostgreSQL
      repository, with version-aware reads;
    - migration `0023`, in which each version is valid only with its exact constants and
      the reverse is guarded;
    - three new test files;
    - the README, the glossary and the capability layer.
    - `policy.py` (v1) and its tests are unchanged.
  - **Owner decisions during implementation:**
    - overlapping schedule fallbacks keep their planned times and are marked
      `overlap`/`weak` (PR #147);
    - plans that cannot yield a suggestion of at least 60 s are skipped and counted under
      `no_coverage`, as in v1.
  - **Changed existing assertions:** four, all pre-authorized.
    - `0023` added to three migration-order lists;
    - the new-run policy version changed from "1" to "2" in the API test.
  - **Review:** `directive-reviewer` returned FIX-FIRST twice, then APPROVE.
    - F1: after a schedule fallback, a changeover could be reused as the start of two
      talks, or as the end of two talks.
    - Fix: a start/end-aware cursor, with regression tests.
    - F3, introduced by the F1 fix: the cue bonus was deduplicated per changeover, which
      dropped the next talk's start cues at a shared changeover. The owner fixed it:
      strength is counted once per changeover, and cues are counted per observed edge.
      A regression test covers it.
  - **Tests (host), after the F1 and F3 fixes:** full backend suite **2,871 passed, 0 failed,
    2 skipped**. Ruff and Pyright clean.
  - **Remaining work:**
    - Accuracy Run 002 (owner step): v1 and v2, with and without transcript cues. The
      corpus is now transcribed, and a first cue analysis found that changeover or cue
      evidence lies within 60 s of 54 of 56 true edges.
    - Migrate the demo database to `0023` after merge, with a backup first.
  - **Accuracy Run 002 (2026-09-29):** [result](../validation/results/session-suggestions-accuracy-002.md).
    - The acceptance criteria are met at zero drift, and at ±5 min only with transcript
      cues.
    - They are not met at ±10 or ±15 min: recall is 0.68–0.86 and medians reach minutes.
    - ED-0105 stays Approved pending an owner decision among options A, B and C in the
      result.
    - The demo database was backed up (`stageflow_demo-pre-ed0105-0023-*`) and, with the
      owner's explicit approval, migrated to `0023` on 2026-09-29.
    - **Disposition:** the owner chose Option B (Phase 2c, ED-0106). ED-0105's
      implementation is complete; its drift acceptance is superseded by ED-0106.
- **Phase 2c (ED-0106), implemented revision:** `6c4e41c`, merged in PR #151 (`main`
  `1e54ff4`). Codex implemented it and the owner committed it.
  - **Changed files:**
    - `policy_v3.py` (new);
    - the session-suggestion contracts, service, repository, in-memory repository,
      serialization and API;
    - the PostgreSQL repository and migration registry;
    - migration `0024` (forward and reverse);
    - the context README, capability layer and glossary;
    - tests: `test_session_suggestion_policy_v3.py`, `test_stage_schedule_offset.py`,
      `test_session_suggestions_policy_v3_postgres.py`, plus pre-authorized updates.
  - **Changed existing assertions:** all pre-authorized.
    - `0024` added to the migration-order lists in three test files;
    - the new-run policy version changed from "2" to "3" in the v2 policy test and the
      API test. The v2 policy test's v1 construction clears the v3-only blocks.
  - **Review:** `directive-reviewer` returned FIX-FIRST, then APPROVE.
    - The finding: nothing tested that the latest applicable override entry wins.
    - The fix was test-only. It adds a precedence test, proven by an in-memory mutation
      check, and an overlapping-talks block case.
  - **Tests (host):** full backend suite **2,910 passed, 0 failed, 2 skipped**. Ruff and
    Pyright clean. CI green.
  - **Demo database:** backed up (`stageflow_demo-pre-ed0106-0024-*`) and migrated to
    `0024` with the owner's approval.
  - **Accuracy Run 003 (2026-09-29):**
    [result](../validation/results/session-suggestions-accuracy-003.md).
    - Every approved numeric target is met.
    - The override criterion is met within 1.1 s in 7 of 8 cases. The exception is
      two-part lateness at ±30 min (7 s): a shrunken planned break kept the day as one
      block, and an override entry cannot split a block.
  - **Status:** Completed.
  - **Follow-up candidate, not yet prioritized:** let override entries act as block
    boundaries. This needs a new policy version.
