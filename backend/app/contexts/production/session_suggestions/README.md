# Session Suggestions

Execution classification: Green under the approved Phase 2/2b/2c plan, ED-0104 through ED-0106,
including the owner decision exempting schedule fallback edges from monotonicity. This context
implements advisory suggestions only. Kernel code and its Session, association and package
semantics remain unchanged. There is no automated realization or ADR-0026 activation.

`policy.evaluate` remains the unchanged pure v1 evaluator for recorded runs. Policy
`boundary-suggestion` v1 freezes these lineage constants:

| Rule | v1 value |
| --- | --- |
| Merge freeze gaps | <=15 seconds |
| Freeze or recording-gap changeover | >=30 seconds |
| Planned edge search | +/-20 minutes, inclusive |
| Scheduled interval duration | >60 seconds |
| Competing-edge cue preference | Edges within 60 seconds of nearest edge |
| Start cue support | -120/+180 seconds, inclusive |
| End cue support | -180/+60 seconds, inclusive |
| Unscheduled covered activity | >=120 seconds |
| Plausible recorder clock | Overlaps planned Stage span expanded +/-12 hours |

Coverage is the union of placed assets. Freeze and silence offsets and phrase-match
first-word offsets are placed on that same recorder clock. Silence overlapping the
changeover and nearby cues are support, not requirements. Equal choices use absolute
plan distance, timestamp and edge kind for stable ordering. With no nearby edge, planned
times clip to coverage; no coverage yields no scheduled suggestion. Missing planned times
yield only unscheduled activity. Withdrawn expectations are not matched.

Adjacent overlapping suggestions use a shared changeover where both resulting durations
remain valid. Otherwise times remain and overlap is explicit. Both observed edges with
support are strong, both without support medium; schedule edges, unresolved overlap and
unscheduled activity are weak. Unscheduled suggestions cover the remaining activity after
subtracting changeovers and scheduled suggestions. All consulted usable timing,
segmentation and transcript references are retained (including evidence outside an
individual result's interval); qualifications are retained without upgrading clocks.

Recorded v2 runs use pure `policy_v2.evaluate` and `boundary-suggestion` v2. v1 constants and
records stay exact and readable; migration `0023_session_suggestions_policy_v2` admits
each version only with its own full constants, retaining the composite suggestion/run
policy FK. v1 durations remain >60 s; v2 permits exactly 60 s. Reverse 0023 refuses while
any v2 run or suggestion exists, and otherwise restores the original v1 constraints
without rewriting history. Reverse before reverting code; v2 rows prevent that rollback.

v2 keeps placement, clock plausibility, <=15 s freeze merging, cue windows, the inclusive
+/-20 min candidate window and >=120 s unscheduled activity. Its changes are:

- Merged freezes must be >=60 s; coverage gaps remain >=30 s. Coverage bounds are edges.
- Freeze strength is `min(length, 600 s) / 60 * (1 + 2 * silent_share)`;
  silence is unioned before calculating the overlap fraction. Gap strength is
  `min(length, 600 s) / 60`; coverage bounds have strength 30.
- A Stage's current planned expectations are ordered by planned start then ID and aligned
  jointly. A talk uses changeover end j and changeover start k > j, >=60 s apart;
  the next observed start uses k' >= k. No two talks share a start edge or an end edge,
  even across fallbacks. Each changeover contributes its strength once, including when
  shared; each observed edge adds 1 per supporting cue in its own window. Each observed
  edge costs `abs(edge - plan) / 30 s`. Rational arithmetic makes exact score ties
  deterministic.
- A missing feasible edge falls back to its planned timestamp, without clipping, with
  score 0 and kind `schedule`. Fallbacks never advance the evidence cursor. If neither
  edge can form a valid pair for a predecessor, both planned edges are retained for that
  predecessor. Existing no-coverage skips remain. If no viable interval meets the
  minimum duration, the talk is skipped and counted under `no_coverage`, as in v1
  (owner decision after the second ED-0105 Yellow stop); it is never silently dropped.
- Ties prefer the earliest edge sequence, then lowest Program Expectation ID. The dynamic
  program keeps the best path per last evidence position (end of talk at changeover c =
  2c, start of talk at c = 2c+1), uses backpointers and ranks for
  ties, and takes O(T*C^3) time and O(T*C) space for T talks and C changeovers (per Stage).
  About 50 changeovers/day is the expected practical workload. Inputs remain bounded at
  10,000 assets and 10,000 expectations; this is not a claim of constant cost at that cap.
- Monotonicity applies to freeze, gap and coverage edges only. Fallback times stay planned;
  any resulting overlapping suggestions are both marked `overlap` and `weak`. Observed
  intervals otherwise do not overlap. There is no post-alignment boundary repair.
- Silence supports an edge only at silent share >=0.3; cue support uses the v1 windows.
  Both observed edges with support are `strong`, both without support `medium`;
  schedule edges, overlapping suggestions and unscheduled activity are `weak`.

The policy still consumes a single Stage snapshot; repositories supply that scope.

New runs use `policy_v3.evaluate`: v2 evidence, strength and joint alignment with one
schedule offset per block. v1 and v2 policy modules and their constants remain intact.
Blocks retain printed-plan order (start, then ID); a planned gap from the preceding end
of >=1,200 s starts a new block. No incomplete or withdrawn expectation enters a block.

For each block, the estimator sums the best nearby changeover support for every shifted
planned edge: `strength * (1 - distance / 180 s)` within +/-180 s. Starts use changeover
ends; ends use changeover starts. It subtracts `abs(offset) / 600 s`. The search evaluates
-3,600 through +3,600 s every 60 s, then +/-60 s around the best every 10 s, clipped to
the same search bounds. Ties prefer smaller absolute offset, then smaller signed offset.
All comparisons use Fraction and integer microseconds; only the recorded margin is
converted to a bounded finite number (0..600,000, the 10,000-talk support ceiling).
The estimate must improve on zero by >=6 points per talk; otherwise source is `none`
and offset zero. Coverage and gap strengths are exactly v2's, and cues do not affect
estimation. No planned talks produce no blocks; absent changeovers produce zero offsets.

A producer override takes precedence. Its Event/Stage-scoped immutable version holds
0..20 entries with strictly increasing aware `effective_from` times on the printed-plan
scale and integer offsets -7,200..+7,200 s. Each block uses the last entry effective at
its first printed start. Earlier blocks still estimate; an empty version clears overrides.
Command ID plus request digest protects replay, including after subsequent versions.
Run digests include the current setting version even when empty or not applicable to
any block. A block records the applicable version only when its source is `producer`.

Alignment uses the shifted plan for eligibility, distance and the unchanged +/-20 min
window. Clock plausibility filtering still uses the printed plan. Block order is not
resorted after shifting. Suggestion start/end plan offsets remain relative to the printed
plan; v3 adds `schedule_offset_seconds` and `schedule_offset_source`. Unscheduled v3
suggestions use zero/`none`. An offset never independently increases strength.

Estimation evaluates at most 134 offsets per block, costing O(134*T*C) time and O(T+C)
space for T talks and C changeovers; v2 alignment still costs O(T*C^3) time and O(T*C)
space. The synthetic 12-talk/~50-changeover test checks completion within seconds.

Migration `0024_session_suggestions_policy_v3` preserves exact v1/v2 constraints, admits
only exact v3 constants, and requires v3 components (null for older versions). Immutable
run blocks retain ordinal, first/last printed starts, talk count, offset/source, estimated
score margin and override version. Immutable setting headers and ordered entries retain
override history. Deferred membership checks prevent appending to a committed setting
or run. Reverse refuses any v3 run or override setting; otherwise it removes the additions
and restores exactly the v2 checks. No existing identity or lineage is rewritten.

`SessionSuggestionService` owns human run/confirm/reject commands. Runs are idempotent by
the input digest while that run is still the Stage's latest, independent of actor and
invocation time; returning to earlier inputs creates a new latest run. At most 10,000 assets and
10,000 expectations are accepted; overflow is a typed refusal, never truncation. Skip
counts fit a nonnegative signed 32-bit integer. Pagination is UUID keyset order with a
limit of 1-100. Rejection reasons contain 1-500 trimmed characters. All domain timestamps
are aware; infrastructure timestamps come from the injected clock.

Only open suggestions can receive a new decision. Confirm checks current expectation
revision/lifecycle/Stage and any Session already linked to that expectation. It invokes
the existing Kernel start and end commands with UUIDv5 IDs derived from the confirm
command ID, then writes the immutable decision with the Session ID and times used.
Same-command replay checks a request digest and returns the original decision even after
supersession. Adjusted times require start < end. No adjustment mutates the suggestion.

The PostgreSQL adapter binds existing Kernel repository calls to a borrowed connection;
the suggestion transaction alone commits/closes it. Event-scoped advisory locks serialize
runs, offset settings and decisions. Suggestion reads and runs take no Stage or Program
Expectation row locks, so live Kernel commands are never blocked by them. Only confirm
and reject lock all Event Stage rows in ID order against concurrent Kernel starts, and
share-lock Program Expectation rows against refresh during the decision.
The two Kernel commands and decision commit atomically; a crash rolls them all back.
Memory simulates the same unit of work under the memory Kernel's lock; it is not durable
and is never a fallback. Migration 0022 reverses only when all three new tables are empty;
ordinary confirmed Sessions are retained.

API base: `/api/v1/session-suggestions/events/{event_id}`. Routes:

- `POST /stages/{stage_id}/runs` (actor and optional cue-list ID/version pairs).
- `POST /stages/{stage_id}/schedule-offset` (actor, command ID, ordered entries).
- `GET /stages/{stage_id}/schedule-offset` (`current`, null before the first version).
- `GET /stages/{stage_id}/schedule-offset/history` (after version, limit 1..100;
  ascending version order and `next_after`).
- `GET /stages/{stage_id}/suggestions` (status, after UUID, limit).
- `GET /suggestions/{suggestion_id}` (components and derived status).
- `POST /suggestions/{suggestion_id}/confirm` (actor, command ID, optional start/end).
- `POST /suggestions/{suggestion_id}/reject` (actor, command ID, reason).

All routes use existing API authentication. Cue lists must belong to the same Event.
Missing resources return 404, stale/realized/not-open or command conflicts 409, invalid
bounds/authority 422, unavailable persistence 503. No media paths or transcript text are
returned. No UI, Work Queue item, boundary proposal or dependency is added.
Run responses include `blocks` and `override_setting_version`; v3 suggestion responses
include both schedule offset components. v1/v2 suggestion components remain unchanged.

Tests: `test_session_suggestion_policy.py`, `test_session_suggestions.py`,
`test_session_suggestions_api.py`, and `test_session_suggestions_postgres.py` cover the
policy, immutable lineage, decisions/replay, import boundary, API and real SQL rollback.
Corpus accuracy and event readiness remain separate owner qualification work.

## Anonymous accuracy evaluation

`evaluation.evaluate_accuracy` accepts suggestions (Candidate/SessionSuggestion or Span)
and anonymous ground-truth Spans for one Stage. It matches chronologically, one-to-one,
with interval IoU >=0.5, maximizing matched count and then minimizing total absolute edge
error; ties retain earlier intervals. Recall is matched/truth, or 0 with no truth.
Median and nearest-rank p95 (`ceil(0.95*n)`) start/end errors cover matched pairs only;
no matches yields null errors. `count_within_60_seconds` requires both edges <=60 s.
Extra suggestions cannot increase recall through duplicate matches. Matching takes
O(G*S) time and space for G truth intervals and S suggestions.

Run from `backend` with both local files outside the repository:

```text
uv run --no-sync python -m app.contexts.production.session_suggestions.evaluate_cli <ground-truth.json> <suggestions.json>
```

Each file is a JSON array of objects with `start` and `end` ISO-8601 timestamps, including
a timezone; additional fields are ignored. The CLI reads files only and prints aggregate
numbers/nulls, never timestamps, paths, names, IDs or source data. Argument/input/read errors
return exit 1 with `{"error_count": 1}`. This evaluator is pulled forward from Phase 5; it does
not generate corpus suggestions or perform a transcription run. Owner Accuracy Run 002
and its drift comparisons remain external qualification work. Real-event data and scripts
stay outside the repository as required by the plan's corpus-handling rules.
Accuracy Run 003 uses the unchanged evaluator with v3 candidates; drift models and the
real corpus harness stay external. Its owner acceptance remains outstanding.

Additional synthetic tests: `test_session_suggestion_policy_v2.py` covers joint alignment,
shared changeovers, drift, thresholds, cues, fallback overlap and version lineage;
`test_session_suggestion_evaluation.py` covers hand-computed metrics and sanitized CLI IO;
`test_session_suggestions_policy_v2_postgres.py` proves exact per-version SQL constraints,
round trips, registry ordering and guarded reversal in a rolled-back transaction.
`test_session_suggestion_policy_v3.py` covers block estimation, overrides, exact scores,
ties, bounds, printed offsets, v2 equivalence under a zero override and full-day cost.
`test_stage_schedule_offset.py` covers bounded commands, concurrency, rollback, immutable
history, digest changes, Event scope and authenticated API responses.
`test_session_suggestions_policy_v3_postgres.py` covers persistence/restart, per-version
constants/components, immutable membership, ordered entries and both reversal guards.
