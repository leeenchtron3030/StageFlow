# Session Suggestions

Execution classification: Green under the approved Phase 2 plan and ED-0104. This context
implements advisory suggestions only. Kernel code and its Session, association and package
semantics remain unchanged. There is no automated realization or ADR-0026 activation.

`policy.evaluate` is pure. Policy `boundary-suggestion` v1 freezes these lineage constants:

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
runs and decisions. Suggestion reads and runs take no Stage or Program Expectation row locks,
so live Kernel commands are never blocked by them. Only confirm and reject lock all Event
Stage rows in ID order against concurrent Kernel starts, and share-lock Program Expectation
rows against refresh during the decision.
The two Kernel commands and decision commit atomically; a crash rolls them all back.
Memory simulates the same unit of work under the memory Kernel's lock; it is not durable
and is never a fallback. Migration 0022 reverses only when all three new tables are empty;
ordinary confirmed Sessions are retained.

API base: `/api/v1/session-suggestions/events/{event_id}`. Routes:

- `POST /stages/{stage_id}/runs` (actor and optional cue-list ID/version pairs).
- `GET /stages/{stage_id}/suggestions` (status, after UUID, limit).
- `GET /suggestions/{suggestion_id}` (components and derived status).
- `POST /suggestions/{suggestion_id}/confirm` (actor, command ID, optional start/end).
- `POST /suggestions/{suggestion_id}/reject` (actor, command ID, reason).

All routes use existing API authentication. Cue lists must belong to the same Event.
Missing resources return 404, stale/realized/not-open or command conflicts 409, invalid
bounds/authority 422, unavailable persistence 503. No media paths or transcript text are
returned. No UI, Work Queue item, boundary proposal, corpus harness or dependency is added.

Tests: `test_session_suggestion_policy.py`, `test_session_suggestions.py`,
`test_session_suggestions_api.py`, and `test_session_suggestions_postgres.py` cover the
policy, immutable lineage, decisions/replay, import boundary, API and real SQL rollback.
Corpus accuracy and event readiness remain separate owner qualification work.
