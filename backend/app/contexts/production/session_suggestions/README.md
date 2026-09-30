# Session Suggestions

This context implements advisory suggestions only. Kernel code and its Session, association and package
semantics remain unchanged. There is no automated realization or ADR-0026 activation.

## Boundary proposals for realized Sessions

The approved Phase 3 backend plan is Green and implementation-ready. Runs evaluate the
unchanged v3 policy, retaining realized talks in joint alignment. For each candidate
linked by Program Expectation to a Session in the Event, each non-`schedule` edge is
compared with that Session's **current** boundary. An absolute difference of at least
30 seconds creates a Kernel `SessionBoundaryProposal`; smaller differences and absent
current boundaries (an active Session's end) are skipped. Unlinked Sessions are excluded.
The proposal freezes the candidate's deduplicated segmentation and timing evidence IDs;
an empty evidence set is skipped. It is `derived`, policy `boundary-suggestion` / `3`.
The fixed system proposer is UUIDv5 using `NAMESPACE_URL` and the exact name
`stageflow:session-suggestion:boundary-proposer` (see `SYSTEM_PROPOSER_ID`).

Each edge has one bounded reason: cue support takes precedence as `cue_supported`;
otherwise `freeze` maps to `changeover_edge`, `gap` to `recording_gap`, and `coverage`
to `recording_boundary`. `schedule` is always excluded, even if cue-supported.
These are explanation codes, not additional policy constants or authority.

An open proposal has no decision and is not stale. Staleness means a boundary-history
entry for the **same edge** has `decided_at > proposed_at`, or a newer proposal exists
for that Session and edge, even if the newer proposal was decided. Newness follows the
existing Kernel order `(proposed_at, boundary_proposal_id)`; ID breaks clock ties.
Open reads return at most two proposals. Under the owner's ED-0112 review decision
(2026-09-29), production skips an edge when its latest proposal, whether undecided,
dismissed or applied, has the same `boundary_at` and policy version and no same-edge
boundary-history correction after its `proposed_at`. Dismissal therefore survives an
unrelated change such as applying the other edge. A changed candidate time or a later
same-edge correction permits a new proposal, subject to the existing threshold and
evidence gates. Older proposals never deduplicate in place of the latest proposal.
The run's `boundary_proposals_created` counts inserts, with legacy runs
defaulting to zero. Identical-input replay returns the original run and count. Linked
Session IDs, revisions and current boundaries participate in the run digest so a human
correction (including a correction back to earlier times) forces reevaluation.

Runs hold the existing Event advisory lock and lock only linked Session rows while
reading current boundaries and producing proposals. Proposals go through the existing
Kernel service and commit with the run. Human apply/dismiss commands serialize on command,
Event and Session, replay by command ID plus request digest, and refuse
`boundary_proposal_decided` or `boundary_proposal_stale`. Apply calls only the existing
Kernel correction, using UUIDv5 `kernel_operation_id(command_id, "apply-boundary")`,
then writes the decision last in the same borrowed transaction. Failure rolls back
the correction and decision together; retry cannot duplicate a correction. Dismiss
only records a decision, with an optional trimmed 1–500 character, NUL-free reason.
Nothing applies automatically; association is not rerun.

Authenticated routes under `/session-suggestions/events/{event_id}`:

- `GET /sessions/{session_id}/boundary-proposals`: open proposals, at most one per edge.
- `POST /sessions/{session_id}/boundary-proposals/{proposal_id}/apply`: human actor and command ID.
- `POST /sessions/{session_id}/boundary-proposals/{proposal_id}/dismiss`: same, optional reason.
- `GET /sessions/{session_id}/boundary-proposals/history`: decision pages, ordered by command
  UUID, `after` UUID cursor and `limit` 1–100 (default 50), with `next_after`.

History items include `proposal_id`, `session_id`, `kind`, `command_id`, `actor_id`,
`decided_at`, `reason`, and `boundary_kind` (`start` / `end`). Under the owner's ED-0113
scope addition (2026-09-29), the history read joins the immutable Kernel proposal by
proposal ID in PostgreSQL and memory; it does not infer the edge from current/open
proposals or the bounded Kernel status snapshot. The existing page bound, UUID order,
Event scope and all prior fields are unchanged. Apply/Dismiss responses and stored
records are unchanged; this addition requires no migration.

Both run and latest-run documents expose `boundary_proposals_created`. All proposal and
history reads validate the Session's Event. Errors retain 404/409/422/503 conventions.
Migration `0027_boundary_proposal_decisions` adds append-only decisions, unique proposal
and command identities, proposal/Session scope enforcement, and the nonnegative run
count. Reverse locks the decision table and refuses while any decisions exist; otherwise
it drops the table, function and count, preserving all Kernel proposals and identities.

Synthetic tests in `test_session_boundary_proposals.py` cover production, threshold and
reason mapping, deduplication, atomicity, current-boundary reevaluation, stale reads,
apply/dismiss, replay and concurrency. `test_session_boundary_proposals_api.py` covers
authentication, scope, bounds, refusals and count disclosure.
`test_session_boundary_proposals_postgres.py` covers durable round trips, transaction
rollback, decisions, staleness, immutability, forward/defaults/reverse/guard, using an
entirely rolled-back schema. `test_session_suggestions.py::test_kernel_import_boundary`
includes the Kernel PostgreSQL adapter and recursively checks Kernel modules.

## Boundary cue presets and composition

The approved Phase 2d-1 plan and accepted cue phrase catalog v1.0 authorize the backend
composition boundary. `cue_catalog.BOUNDARY_CUE_CATALOG` is pure and recursively immutable:
11 profiles, 18 groups and three regional add-ons, with exact literal text, roles,
default flags and evidence labels. `take {n}` and `scene {n}` each expand to 40 phrases
(1–20 as digits and English words). Deferred ceremonies/worship groups are absent.
Import validation reuses the Editorial phrase rules, rejects duplicate keys and normalized
phrases within groups, and checks profile references. The digest hashes canonical JSON
with sorted object keys and compact separators, retaining catalog array order.

`cue_composition.compose` selects submitted groups in catalog order, adjusts defaults
with explicit group/literal-phrase choices, then adds custom phrases in submitted order.
Exclusion removes a phrase only from its selected source group, so the future UI's
"remove phrase" action must exclude it from every source group to remove it entirely.
The optional profile key records provenance only. `word_tokens` defines deduplication;
role union puts changeover phrases in both lists. Segment phrases retain their source
groups and are stored without publication. Custom roles are start/end/changeover only.
Every published list must contain 1–200 phrases; `cue_list_empty` and
`cue_list_too_large` report the affected role and count, with no truncation.

`BoundaryCueService.publish` is a human command, serialized per Event in the existing
suggestion transaction. Both reserved lists (`boundary-cues-start`, `boundary-cues-end`)
and the composition commit together. List IDs remain stable across versions, as in
ED-0092; each composition freezes both ID/version pairs. Manual ED-0092 publication
refuses these keys. Command ID plus request digest provides original-result replay and
body-conflict refusal. The injected clock supplies the aware composition timestamp.
Catalog identity/digest, profile, group versions, choices, customs and segment sources
are first-class provenance. Highest version is current; history is immutable.

Migration `0025_boundary_cue_composition` adds only the composition header and four
child tables. Immutable triggers reject update/delete; deferred membership checks also
refuse incomplete publication or later child inserts. Forward refuses any pre-existing
reserved list key. Reverse refuses any composition and otherwise drops exactly its
tables/functions/registry entry; existing Editorial lists are untouched. Applying the
migration to the Demo database remains an owner-authorized operation with a backup.

Runs naming neither cue list use both current-composition references. Naming either
list preserves the explicit request without filling the other. Without a composition,
neither default is supplied. Run lineage and input digests freeze the actual references;
changing composition never automatically reruns suggestions.

Authenticated routes under `/session-suggestions/events/{event_id}`:

- `GET /boundary-cue-catalog`: versioned catalog and digest (no persistence required).
- `POST /boundary-cues`: catalog version, optional profile key, group keys, include and
  exclude choices (`group_key`, `phrase`), custom phrases (`text`, `role`), actor and
  command ID. Requests allow at most 20 groups, 400 choices of each kind and 400 customs;
  published lists retain the stricter 200 limit. Unknown or mismatched choices fail.
- `GET /boundary-cues`: current composition, or `null`.
- `GET /boundary-cues/history`: ascending version pages; `after` 0–2,147,483,647,
  `limit` 1–100 (default 50), with `next_after`.

Composition reads/publication require an existing Event. The existing run response adds
`start_cue_list` and `end_cue_list` with `id`/`version`. Errors follow the existing
404/409/422/503 conventions; list-size errors have structured `code`, `role`, `count`.
No UI, dependency, policy, Kernel command or authority change is included.

Tests: `test_boundary_cue_catalog.py` compares every accepted literal/role/default/evidence
row and template expansion; `test_boundary_cue_composition.py` covers merge, bounds,
provenance, atomic rollback, replay/concurrency, D1 and D2; `test_boundary_cue_api.py`
covers authentication, bounded input/history and run-reference disclosure;
`test_boundary_cue_postgres.py` covers persistence/restart, transactional rollback,
immutable membership and both migration guards in a rolled-back schema.

## Suggestion policies

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

### Pure boundary-evidence prototype (v5)

`policy_v5.evaluate(snapshot, override=None)` exposes `boundary-suggestion` version 5
for local harness evaluation. The approved Phase 7 work is Green and implementation-ready;
its scope is the pure prototype. The service still imports v3. V5 is not registered as a
persistable run policy, and this prototype changes no API, migration or runtime setting.

V5 retains printed-plan clock filtering and imports v3's `schedule_blocks` unchanged,
including block ordering, estimation and producer-override precedence. Estimation sees exactly
v3's weighted changeovers, including strength-30 coverage bounds, before cue edges are
added. The reduced coverage strength applies to alignment only; otherwise coverage
changes would silently change the offset estimator as well. All other v3 constants
are inherited by `PolicyV5`; the v5 starting values live only in `policy_v5.py`:

| Module constant | PolicyV5 field | Value |
| --- | --- | --- |
| `CUE_RADIUS` | `cue_radius` | 30 seconds |
| `CUE_WEIGHT` | `cue_weight` | 10 |
| `CUE_EDGE_GAP` | `cue_edge_gap` | 30 seconds |
| `CUE_EDGE_STRENGTH` | `cue_edge_strength` | 3 |
| `COVERAGE_STRENGTH_V5` | `coverage_strength` | 5 |
| `OUTSIDE_PROGRAM_MARGIN` | `outside_program_margin` | 1800 seconds |

For each matching-role hit within the inclusive radius, edge support adds the exact
Fraction `10 * (1 - abs(hit - edge) / 30 seconds)`, using integer microseconds.
Cue helpers normalize aware times to UTC, preserving distinct daylight-saving folds.
A hit exactly 30 seconds away contributes zero and does not set the support flag.
Start/end hits support their respective role. Changeover hits support both the end
and start of freeze/gap changeovers, measured separately against each edge; they do
not create cue edges or support coverage bounds. Segment phrases and studio
"take/action/cut" matches never enter Session-role timestamp lists. The pure contract
carries classified times, not text; callers must respect the accepted catalog roles.
The service's cue wiring remains a later step.

`AssetInput` retains its existing `start_cues` and `end_cues` datetime tuples. It adds
`changeover_cues`, `specific_start_cues` and `specific_end_cues`, all defaulting empty.
The latter two are subsets of their role's hit times: membership represents the
per-cue `specific` flag without changing the old timestamp element type. Equal-time
hits retain their count; specificity applies to that role/time. Inputs detach supplied
sequences into tuples and reject naive times or specificity outside the role's hits.
Specificity is an explicit caller fact, not inferred from timestamps or a new catalog rule.

Cue clusters are formed in chronological order, greedily collecting hits no more than
60 seconds from the first hit (inclusive), then beginning the next cluster. This does
not chain a long series through adjacent hits. Two or more hits qualify; a singleton
qualifies only if specific. Start edges use the earliest cluster hit, end edges the
latest, preserving the outward extent of evidence for the talk. An eligible cluster
creates `EdgeKind.CUE` only if no freeze/gap edge of that same role is within the
inclusive 30-second gap of that chosen timestamp. Coverage does not suppress cue
creation. A cue edge is available only for its own role, within the inclusive shifted
+/-20-minute planned-edge window. Its strength is 3. Any suggestion using a cue edge
is at most medium; schedule/overlap/unscheduled cases stay weak.

A cue edge also receives its own cluster hits' proximity support: a hit at distance
zero adds the full `CUE_WEIGHT`, so a single-hit edge scores
`CUE_EDGE_STRENGTH + CUE_WEIGHT` (3 + 10), and a two-hit cluster up to 3 + 20 before plan cost.

Coverage bounds have alignment strength 5 and are fallback candidates **per planned
edge and role**: if any freeze, gap or eligible cue edge is inside that edge's shifted
+/-20-minute window, every coverage candidate for that role is excluded. This check
happens before predecessor/cursor feasibility, not after an observed edge loses an
alignment comparison. Otherwise coverage candidates still need to be inside that
same window. Schedule fallback placement and overlap handling stay v3's.

The v5 adapter calls the actual imported v2 `align`, preserving its shared-changeover
strength, recurrence, evidence ordering and tie-breaking. Per-call `_WindowedEdges`
views mask excluded timestamps only during v2's once-per-talk candidate enumeration;
indexed edges retain their real timestamps for scoring and results. Exact Fraction
bonuses replace counts through v2's unchanged unit cue multiplier. Tests protect this
interface, role separation and replay; no policy globals are patched. Freeze/gap
weighting and silence support import v2; placement, evidence lineage and candidate
construction follow v3.

After scheduled spans and real changeovers are subtracted, remaining activity of at
least 120 seconds is suppressed only when its start is **strictly after** the latest
shifted planned end plus 1800 seconds, or its end is **strictly before** the earliest
shifted planned start minus 1800 seconds. Each current complete expectation contributes
its printed times plus its own applicable block offset; the min/max are taken after
shifting, even when block offsets differ. Exact margins remain eligible. With no
complete plan there is no program-span filter. Each suppressed remaining interval
increments `outside_program` once; no clipped replacement is created.

`SkipCounts.outside_program` defaults to zero without entering legacy dataclass fields.
The pure `SkipCountsV5` subtype promotes it to a validated field for v5 results and
harness output. Legacy SQL positional writes, row-key reads and API skip documents
therefore retain their existing shape, and v1-v3 report zero through the default attribute.
V5 is not passed to persistence. Without cues, only coverage fallback/strength and
the unscheduled program-span filter differ from v3; the unchanged-scenario comparison
and isolated coverage/program fixtures prove this reduction.

`test_session_suggestion_policy_v5.py` covers the exact weights, roles, clusters,
specificity, gap/window/margin boundaries, offset and coverage behavior, immutable
inputs, legacy skip mapping, no-cue reduction, and deterministic 30-talk/80-changeover/
200-cue evaluation within 10 seconds. These constants are starting values for owner
measurement, not a corpus qualification or readiness claim.

`SessionSuggestionService` owns human run/confirm/reject commands. Runs are idempotent by
the input digest while that run is still the Stage's latest, independent of actor and
invocation time; returning to earlier inputs creates a new latest run. At most 10,000 assets and
10,000 expectations are accepted; overflow is a typed refusal, never truncation. Skip
counts fit a nonnegative signed 32-bit integer. Pagination is UUID keyset order with a
limit of 1-100. Rejection reasons contain 1-500 trimmed characters. All domain timestamps
are aware; infrastructure timestamps come from the injected clock.

New runs retain realized Program Expectations in the unchanged v3 policy input, then
omit candidates whose expectation has a Kernel Session on any Stage of the Event.
This is the same realization rule used by confirm. Their evaluated spans still cover
scheduled activity, so filtering does not create unscheduled replacements or shift other
talks' alignment. Rejected talks remain eligible on a new run. The sorted set of realized
expectation IDs joins the input digest, so confirm followed by run creates a new run.

The informational skip `already_realized` counts omitted candidates. Migration
`0026_session_suggestions_already_realized` adds a nonnegative integer column with default
0; old rows read 0, and reversal drops only that column and its migration record.
Run and latest-run responses include the skip. The Stage summary shows "1 already a
Session" or "N already Sessions" when nonzero, outside the exception-style skips list.
Work Queue counts reflect only stored open suggestions. No policy constants or version,
Kernel semantics, dependency or runtime configuration change accompanies this filter.

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
- `GET /stages/{stage_id}/runs/latest` (latest by recorded run sequence, including
  empty runs; `suggestion_run_not_found` 404 before the first run).
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
returned. No UI, boundary proposal or dependency is added.
Run responses include `blocks` and `override_setting_version`; v3 suggestion responses
include both schedule offset components. v1/v2 suggestion components remain unchanged.

The latest-run read returns the same run document as the run command: ID, Event/Stage,
actor, creation time, policy ID/version/constants, input digest, skips, blocks (ordinal,
first/last printed start, talk count, offset/source/margin and override version), overall
override version and start/end cue-list references. It does not run the policy again.

## Producer Work Queue read

The Event-scoped `list_pending_confirmations` port returns one read-only item per Stage
whose latest run has open suggestions (no decision and not superseded). Its projection
ID is `suggestions:<stage_id>`, subject kind `stage_suggestions`, subject ID the latest
run ID, subject revision 1 and Session ID null. The decision type and reason code are
`presentation_confirmation_pending`; `open_count:<n>` and `weak_count:<n>` count only
open suggestions, with counts bounded by the existing signed 32-bit count contract.
Priority is 6, both timestamps are the run's creation time, and the action reference is
`stage:<stage_id>:suggestions`. Decisions change counts without changing that timestamp.
An empty latest run or deciding every suggestion removes the item.

The production-layer `ProducerWorkQueueService` merges this read with Kernel and
Assembly reads, requesting `limit + 1` after the same cursor from each source. The sort
key and v1 cursor remain `(priority, updated_at, projection_id)`. SQL selects only latest
runs, excludes decisions and aggregates counts before the bounded keyset page; no
suggestion history is loaded into the application to compute counts. The Kernel imports
neither capability. No write, migration, task claiming or authority is added.

Any source storage outage returns the existing bounded 503.

`test_session_suggestions_surfaces.py` covers latest-run API lineage/absence/authentication,
queue counts and disappearance, Event scope, three-source ordering/cursors and
bounded failures. `test_session_suggestions_surfaces_postgres.py` covers real SQL latest
v1/v2/v3 reads, blocks, counts, sequence and cursor behavior with rolled-back fixtures.
`test_work_queue_assembly.py` enforces both Kernel import boundaries.

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
`evaluation.match_intervals` exposes the same matches as immutable original-input `(truth_index, suggestion_index)` pairs in chronological order; `evaluate_accuracy` uses it internally.

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
Existing recall, counts, matched-pair errors and within-60 values remain unchanged.
`precision` separately matches scheduled suggestions against truth, divided by scheduled
suggestion count. Bare Spans are treated as scheduled. `unscheduled_count` reports
unlinked suggestions; `precision_including_unscheduled` uses the original all-suggestion
matches divided by all suggestions. Empty denominators give zero. This separate matching
prevents an unscheduled candidate from taking a scheduled candidate's precision match.
`wrong_day_count` counts suggestions with either edge outside the Stage's planned span
expanded by 12 hours (exactly on the margin is allowed). It includes unscheduled
suggestions and must be zero to pass. Without the optional `planned_span` argument it is
null, meaning unchecked; the legacy interval CLI cannot certify the wrong-day target.

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

## Corpus validation harness

For paced replay through the demo APIs and workers, see the [live replay tool](../../../../../scripts/validation/README.md#session-suggestions-live-replay).

The pure harness emits deterministic sanitized metrics and supplies synthetic scenario
regression tests. Versions 1-3 keep their constants and behavior; version 5 is a pure
prototype. Services, storage and runtime settings are unchanged. Real-corpus reproduction
and qualification remain owner-run checks; synthetic tests do not establish event readiness.

The machine-readable contract is [corpus-manifest.schema.json](corpus-manifest.schema.json).
Keep every real manifest, media file, decoded truth, transcript and extraction script
**outside the repository**. Build a UTF-8 JSON object with a `stages` array; each Stage has:

- `blocks`: array of `start` (aware ISO date-time), positive integer `duration_us`, and
  `intervals`: objects with `kind` (`freeze` or `silence`), integer `start_us` and `end_us`
  relative to that block. Optional `start_cues`, `end_cues` and `changeover_cues` are
  arrays of aware absolute timestamps from externally matched transcript cues, or
  objects with an explicit `specific` flag (see the v5 input section below).
- `schedule`: objects with unique anonymous `key`, `planned_start` and `planned_end`.
  Use the actual published schedule for `--schedule-source manifest`; it is used as-is.
- `truth`: objects with `start` and `end`, retaining duplicate truth intervals if present.

Use full `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` or an explicit `+/-HH:MM` offset. Values normalize
to UTC; naive timestamps are refused. Ends must follow starts, segmentation must satisfy
`0 <= start_us < end_us <= duration_us`, and cues must be within their own block (inclusive).
The parser rejects manifests larger than 64 MiB in UTF-8 before JSON decoding, with a
sanitized error. It enforces these relational checks and the schema's structural bounds:
at most 10,000 Stages, blocks, plans, truth intervals, intervals per block, or cues per role;
durations at most 315,576,000,000,000 microseconds. Empty blocks and truth are allowed;
the selected schedule must be nonempty to check wrong-day placement. Extra fields are
rejected. Do not put paths, titles, speaker names, transcripts or other free text in it.
Anonymous keys are checked for uniqueness then replaced with ordinal-based identities.
Schema validation is implemented with the standard library; no package is added.

From `backend`, with an external manifest:

```text
uv run --no-sync python -m app.contexts.production.session_suggestions.harness_cli <external-manifest.json> --policy-version 3 --schedule-source manifest --cue-profile conference
uv run --no-sync python -m app.contexts.production.session_suggestions.harness_cli <external-manifest.json> --policy-version 3 --schedule-source drift --drift-model two-part --magnitude-seconds 900 --seeds 0 1 2 3 4 --markdown
```

`harness.parse_manifest` produces frozen Stage inputs; `harness.run_manifest` runs the
chosen policy (`1`, `2`, `3`, or pure prototype `5`) independently for each Stage. One invocation is
one scenario/model/magnitude; repeat invocations for a matrix. Stages may span multiple
days. Metrics match only within a Stage, never across Stages. Reports use zero-based
Stage ordinals and include each seed plus each metric's worst value **and its seed**;
minimum recall/precision/matched/within-60, maximum errors/other counts, null errors
considered worst, smallest seed on ties. There is no averaged-median aggregate.

For drift schedules, order truth by `(start, end)` and start a new event day when the
gap from the previous truth interval's end to the next start is at least six hours.
Continuous talks crossing UTC midnight stay in one event day. Use Python `random.Random`
(string seed version 2) with exactly:

```text
stageflow:session-suggestions:harness:v1:{model}:{seed}:{stage_ordinal}:{day_ordinal}
```

Day ordinals are chronological and zero-based. The magnitude is an integer in 0..86400
seconds; one to 100 integer seeds are accepted, sorted and deduplicated. Each day has
an independent RNG. Whole-day draws one uniform offset in `[-D, D]` per event day;
two-part draws another before the talk after that day's largest planned break, measured
on the truth-derived plan before drift (earliest break on ties).
For each talk, draw start jitter then end jitter, both uniform in `[-60, 60]` seconds,
and add to its part's offset. This jitter remains at D=0, matching the historical method.
Independent drift draws start then end in `[-D, D]` with no shared offset or extra jitter.
Timedelta rounds to microseconds. Every drift model clamps each planned talk to at least
120 seconds: `planned_end = max(planned_end, planned_start + 120 s)`, as in Runs 002/003.
Generated plans replace the manifest schedule and use truth ordinals.
These documented RNG inputs make new runs reproducible; exact historical Run 003 numeric
reproduction still requires the owner's local corpus and original seed/draw convention.

An optional `--cue-profile` selects catalog groups and composes default phrases through
`cue_composition.compose`. Only phrase counts are output. The harness does not transcribe
or match text: supplied cue times must already represent matches for that composition.
Absent cue times stay absent; without a profile all cue inputs are disabled. To compare
profiles with different matches, prepare separate external manifests.

For v3 or v5, repeat `--producer-offset <aware-ISO-effective-from> <integer-seconds>` in
strictly increasing effective-time order (at most 20; offsets -7200..7200). Entries apply
to each Stage in the invocation via `ScheduleOffsetSetting`; use separate invocations
for different Stage settings. These are explicit producer offsets, not automatically
inferred truth offsets. Existing v3 block/override precedence is preserved.

JSON output contains only closed labels, ordinals, seed numbers, counts, errors, ratios
and target booleans, never source keys, titles, timestamps, cue phrases or paths.
`--markdown` appends numeric per-seed and worst-seed tables after the JSON. A target pass
requires recall >=0.90, median start/end errors <=30 seconds, and wrong-day count zero;
precision is reported without inventing an ADR precision threshold. Exit codes: 0 all
Stage/seed targets met, 2 measured target failure (report still emitted), 1 invalid
arguments/input/read with only `{"error_count": 1}`. `--help` exits 0. Exceptions never
echo values, paths or parser diagnostics. Review sanitized outputs before publishing.

`scenarios.generate_scenario` supplies clean day, recording gaps, multi-part talk,
wrong clock, short evenly spaced talks and late recording start manifests with generic
synthetic intervals only. No media or external files are needed. The short-talk case
deliberately shifts the plan by one periodic slot; current behavior is pinned, not tuned.
`test_session_suggestion_harness.py` covers every scenario's metrics, excluded wrong-clock
lineage, determinism, isolated Stages, manifest bounds/privacy, cues, offsets, precision,
wrong-day margins and CLI exit codes. `test_session_suggestion_evaluation.py` retains the
original metric fixtures and CLI privacy checks.


### V5 harness inputs and synthetic generator

`--policy-version 5` selects the pure prototype; v3 remains the CLI default. Producer
offsets are accepted for 3 and 5 only. The optional `changeover_cues` block array joins
`start_cues` and `end_cues`. Each array accepts the original aware ISO string or an
object `{"at": "2000-01-01T09:00:00Z", "specific": true}`; `specific` defaults false.
The parser projects specificity into the corresponding subset for start/end hits;
changeover specificity has no edge-creation effect. Unknown fields, non-boolean flags,
naive timestamps and hits outside the block are refused with sanitized errors.
Old manifests parse identically. Without `--cue-profile`, all three cue arrays and
specificity subsets are disabled. Profiles still enable pre-matched supplied times;
this harness does not infer text matches, catalog specificity or studio semantics.

The four additional `generate_scenario` names use generic synthetic values:

- `cue-only-edge`: specific end/start hits without a freeze at the first changeover;
- `false-in-talk-end-cue`: a lone nonspecific in-talk end hit;
- `recording-starts-early`: coverage begins before a true start changeover;
- `content-after-program`: a separate recording after the program margin.

`test_session_suggestion_harness_v5.py` pins all ten scenarios' complete v5 metrics
and skips, including the unscheduled interval between cue-only edges and the extra
suggestion in the periodic short-talk case. The original six v3 scenario fixtures
retain their existing assertions. These measurements describe synthetic behavior only.

`realistic_schedule_error(seed, *, talk_count=30, slot_seconds=1500, dropped=False,
added=False, after_program=False, cues=False, cue_recall=0.8, timeline=False)` returns
a manifest **Stage**, wrapped as `{"stages": [stage]}` for parsing. With `timeline=True`
it returns `(stage, relative_second_replay_data)`. This ports the parked generator
without changing its no-cue draws: `Random` uses Python string seeding version 2 with
`stageflow:session-suggestions:realistic:v1:{seed}`. Draw order is initial integer
lateness (-300..300), dropped index, added index, then for every scheduled talk its
integer duration error (-40..40 percent) and changeover jitter (-60..60 seconds),
including dropped talks; an added talk then draws duration (600..1200). Duration error
truncates toward zero; changeovers are 180 seconds plus jitter. A dropped slot consumes
no time; an added talk consumes its duration and a 180-second changeover. Optional tail
content is 900 seconds. Recording blocks span 600 seconds, with clipped holding intervals.

`cues=True` uses an independent Python version-2 string seed
`stageflow:session-suggestions:realistic:cues:v1:{seed}`, leaving the original schedule,
holds and replay data unchanged. For each actual talk in chronological order (including
added/tail activity), draw recall (`random() < cue_recall`) then integer jitter (-10..10)
for start, end, and changeover, in that order. Always draw jitter even if the hit is
omitted. Start uses the true start, end and changeover the true end. Then draw one false
nonspecific end time uniformly among integer seconds from start+60 through end-60.
True hits are marked specific. Hits go into half-open recording blocks once, including
on block boundaries. Recall zero still emits the false hits. No media or transcript
content is generated. Seed 7 draw fixtures and development seeds 1-20 protect the port,
recall bounds, optional edits and determinism; reserved held-out seeds are never used.
