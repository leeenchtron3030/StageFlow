# Session boundary suggestions (ADR-0034)

## Status

Approved (2026-09-28). Phase 1 (ED-0103) and Phase 2 (ED-0104) are complete. Phase 2b (ED-0105,
policy v2) is detailed below (2026-09-29), after the early accuracy check. Phases 3–5 are outlined here; each gets a detailed section, reviewed by the owner, before it starts.

## Execution authority

- Classification: Green for Phase 1 under the accepted ADR. Later phases are Green once
  their detailed sections are approved.
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
| 4. Producer surfaces | Work Queue item "confirm presentation" (additive), and suggestion review on Session Detail and Mission Control under the owner's scanning rule; UX checkpoint | none |
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
