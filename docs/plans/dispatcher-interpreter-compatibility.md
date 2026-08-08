# Dispatcher and Observation Interpreter compatibility

## Status

Completed — original implementation, DIC-001 through DIC-004 corrections, and
DIC-RR-001 through DIC-RR-003 final hardening are implemented. Fresh independent Codex
review on 2026-08-07 recommends acceptance with no remaining findings.

## Related findings or ADRs

- Finding/disposition: ABR-003 and ABR-004 in
  [the architecture-baseline disposition](../reviews/architecture-baseline-disposition.md),
  plus approved decision D-04. The baseline review is supporting evidence only.
- ADR: [ADR-0019](../adr/ADR-0019-stable-ingress-and-interpreter-boundary.md),
  with ADR-0011 and ADR-0015 preserved in `ARCHITECTURE_DECISIONS.md`.
- Engineering Directive or other authority: Product Constitution principles 22-25;
  [architecture principles](../architecture/principles.md) 2, 6-9, and 11;
  [system context](../architecture/system-context.md); and the
  [domain glossary](../architecture/domain-glossary.md).

## Problem statement

`ProductionEventDispatcher` accepts only the legacy concrete
`ProductionEventInterpreter`, calls `can_interpret(event)`, supplies an
`InterpreterContext`, and collects `InterpreterResult`. The six implemented Observation
Interpreters instead expose `can_interpret_event(event)`, accept
`ObservationInterpreterContext`, and return `ObservationInterpreterResult`. Consequently,
the repository's intended Production Event -> dispatcher -> Semantic Observation path
cannot use any concrete Observation Interpreter without a type bypass or compatibility
boundary.

This must be corrected before the dispatcher becomes a runtime ingress boundary. The
correction must not create a second Production Event, obscure non-success states, invent
context, or pre-empt the separate durable-ingress work required by ADR-0019.

## Verified current behavior

- `ProductionEventDispatcher.interpreters` is a sequence of
  `ProductionEventInterpreter`; matching and invocation preserve registration order.
  No-match returns an empty `interpreter_results` tuple and counts every registered
  interpreter as declined.
- A matching interpreter exception currently aborts dispatch. There is no typed
  per-interpreter failure result and no opportunity to retain another matching
  interpreter's successful result.
- `DispatchSummary` currently counts a result as successful solely when it has no
  warnings. It does not inspect interpreter state and would therefore misclassify a
  warning-free failed/limited outcome if one were introduced.
- `InterpreterResult` represents one source Production Event ID, zero-to-many
  Observations, an `InterpreterStatus`, warnings, and metadata. `InterpreterStatus`
  contains `active`, `disabled`, `degraded`, `experimental`, and `archived`.
- `ObservationInterpreterResult` represents one-to-many source Production Event IDs,
  zero-to-many Observations, the concrete interpreter ID, warnings, and metadata. It has
  no result status or structured failure/limitation member; lifecycle state exists on
  the concrete interpreter as `ObservationInterpreterStatus`.
- `ObservationInterpreterStatus` contains `unknown`, `configured`, `ready`, `active`,
  `degraded`, `failed`, `disabled`, and `archived`. Only `ready`, `active`, and
  `degraded` are eligible to match.
- `InterpreterContext` and `ObservationInterpreterContext` currently have identical
  fields and types: correlation ID, current timestamp, optional Recording Block ID,
  optional Stage ID, and metadata. Both shallow-freeze metadata and currently permit
  their default wall clock; the adapter need not use either default.
- All six concrete implementations—recording activity, schedule, media artifact,
  runtime clock, transcript, and vision—support both one Event and a non-empty Event
  sequence. Their current mapping logic is event-local: batch execution iterates the
  supplied Events in order and concatenates their Observations. No interpreter performs
  cross-Event inference or requires a batch for semantic correctness.
- Concrete interpreters preserve the source Event ID in result lineage, and each
  generated Observation carries exact first-class Event/interpreter provenance plus
  compatibility metadata. They create fresh Observation IDs on each execution; stable
  replay identity is part of ADR-0019's broader ingress correction and is not solved by
  adapting the dispatcher alone.
- Public package exports expose `ProductionEventInterpreter`, `InterpreterContext`,
  `InterpreterResult`, `InterpreterStatus`, `ObservationInterpreter`, and all concrete
  interpreter classes. No accepted authority requires removal or deprecation now.
- No `docs/plans/dispatcher-interpreter-compatibility.md` exists in the synchronized
  working tree, HEAD, or visible branch history, despite the reconciliation request
  referring to an initial version. This document therefore restores the requested
  canonical path; claims about the unavailable initial text cannot be verified.

## Desired behavior

One dispatcher routes a single stable Production Event through the smallest typed
dispatcher-facing interpreter protocol. A dispatcher-owned adapter makes each concrete
Observation Interpreter conform without making the dispatcher depend on its concrete
class or turning either domain package into a registry/service locator. Results retain
all Observations, lineage, warnings, lifecycle state, and failures. Registration order
defines deterministic match, invocation, and aggregate-result order.

The dispatcher remains a synchronous deterministic boundary. Future durable ingress
persists/deduplicates a source fact and establishes stable ingress and Production Event
identity before calling it; the dispatcher and adapter neither allocate nor replace that
identity.

## In scope

- Add a structural protocol in the dispatcher package containing only the members the
  dispatcher uses: read-only `id`, `can_interpret(event) -> bool`, and
  `interpret(event, context) -> InterpreterResult`.
- Make `ProductionEventDispatcher` depend on that protocol.
- Add one dispatcher-owned adapter around a typed concrete Observation Interpreter
  protocol, converting the single-Event call, context, result, lifecycle status, and
  failures.
- Represent every concrete lifecycle status without treating unknown, configured,
  disabled, archived, or failed as success.
- Preserve the legacy `ProductionEventInterpreter` public contract and its ability to
  satisfy the new structural protocol without wrappers.
- Correct dispatcher aggregation and summary semantics for no-match, multiple matches,
  warnings/limitations, and failures.
- Add real dispatcher integration tests for all six concrete Observation Interpreters.
- Update affected package READMEs and public exports.

## Out of scope

- Durable ingress records, source fingerprints, databases, schemas, migrations,
  idempotency stores, workers, retries, startup reconciliation, or a composition root.
- Changing how Production Event or Observation IDs are allocated on replay. This plan
  must not claim ADR-0019's durable identity validation is complete.
- Batch dispatch, cross-Event interpretation, provider adapters, discovery/watchers,
  Evidence or later reasoning, and broad package renames/reorganization.
- Removing or deprecating `ProductionEventInterpreter`.
- Changing canonical terminology or treating Semantic Observations as Media Resource
  Observations.

## Constraints

- Architecture and terminology constraints: retain one modular-monolith dispatcher;
  use direct synchronous calls; call inputs Production Events and outputs Semantic
  Observations; the adapter translates contracts and does not interpret, discover, or
  locate services.
- Compatibility constraints: existing imports and behavior of
  `ProductionEventInterpreter`, `InterpreterContext`, `InterpreterResult`, and the six
  concrete interpreter packages remain supported. Enum additions must be additive.
- Offline/event-mode constraints: the bridge performs no I/O or network work and is
  suitable for a future local event-mode composition root.
- Security and data-handling constraints: failure diagnostics must not copy Event
  payloads, metadata, credentials, transcripts, or media into warnings/logs.
- Typing constraints: bridge code may not use `Any`, unsafe casts, `# type: ignore`, or
  runtime duck-typing workarounds. Define explicit `Protocol` members and use Pyright to
  prove all legacy/concrete adapters satisfy them. Existing legacy metadata annotations
  elsewhere do not justify bridge-specific `Any`.
- Identity constraints: preserve the exact input `ProductionEvent.id`, Event
  `correlation_id`, concrete interpreter `id`, Observation provenance/source references,
  warnings, and Observation order. Never construct or mutate a Production Event.

## Implementation approach

1. **Introduce dispatcher-owned structural boundaries.** Add a
   `DispatcherEventInterpreter` protocol under `production/dispatcher` with only `id`,
   `can_interpret`, and `interpret`. Add a second typed protocol describing only the
   concrete adapter's needs: `id`, `status`, `can_interpret_event`, and single-Event
   `interpret` returning `ObservationInterpreterResult`. Do not require names, supported
   type/source lists, rules, policy, mappings, batch predicates, or metadata because the
   dispatcher does not use them.

2. **Own the adapter in `production/dispatcher/compatibility`.** The bridge exists to
   satisfy dispatcher expectations using concrete Observation Interpreter semantics, so
   ownership belongs at the consuming dispatcher boundary. Placing it in the legacy
   `interpreter` package would make that older abstraction own newer concrete semantics;
   placing it in `observation_interpreter` would make the producing domain depend on a
   dispatcher consumer. A dispatcher subpackage preserves dependency direction and
   leaves both interpreter packages free of registration, lookup, or service-location
   responsibility.

3. **Convert context explicitly and losslessly.** The adapter creates
   `ObservationInterpreterContext` from every `InterpreterContext` field without using
   defaults:

   | `InterpreterContext` field | Target | Treatment | Information loss |
   | --- | --- | --- | --- |
   | `correlation_id` | `correlation_id` | Preserve directly | None |
   | `current_timestamp` | `current_timestamp` | Preserve directly; do not call a wall clock | None |
   | `recording_block_id` | `recording_block_id` | Preserve directly, including `None` | None |
   | `stage_id` | `stage_id` | Preserve directly, including `None` | None |
   | `metadata` | `metadata` | Preserve the supplied mapping; target contract freezes its own view | No semantic omission; current nested mutability remains an existing legacy constraint |

   No field is derived or unavailable, and none is intentionally omitted. Event lineage
   remains authoritative: existing concrete context extraction prefers Event references,
   payload, and metadata before Stage/Recording Block compatibility fallbacks. The
   adapter must not synthesize Session, Stage, Recording Block, schedule, media, source,
   ingress, or timing facts.

4. **Make status conversion exhaustive and additive.** Extend `InterpreterStatus` with
   the concrete-only lifecycle values needed for lossless conversion. Use an explicit
   total mapping (not value-based casting) and a test that fails when either enum gains
   an unmapped member.

   | Source status/outcome | Source meaning | Dispatcher-facing meaning | Exact? | Information lost? | Fail closed? |
   | --- | --- | --- | --- | --- | --- |
   | `UNKNOWN` | Lifecycle/readiness is not known; cannot match | `UNKNOWN`; not invoked by normal dispatch | Yes after additive enum value | No | Yes |
   | `CONFIGURED` | Configured but not ready; cannot match | `CONFIGURED`; not invoked by normal dispatch | Yes after additive enum value | No | Yes |
   | `READY` | Ready and eligible to interpret | `READY`; eligible, not rewritten as active | Yes after additive enum value | No | No |
   | `ACTIVE` | Active and eligible | `ACTIVE` | Yes | No | No |
   | `DEGRADED` | Eligible with reduced capability | `DEGRADED`; warnings remain separate | Yes | No | No, but never report as unqualified success |
   | `FAILED` | Interpreter lifecycle has failed; cannot match | `FAILED`; not invoked by normal dispatch | Yes after additive enum value | No | Yes |
   | `DISABLED` | Administratively disabled; cannot match | `DISABLED`; not invoked | Yes | No | Yes |
   | `ARCHIVED` | Retired; cannot match | `ARCHIVED`; not invoked | Yes | No | Yes |
   | Legacy `EXPERIMENTAL` | Legacy interpreter is eligible but experimental | `EXPERIMENTAL`; legacy-only, preserved unchanged | Exact within legacy contract | No | No, but summary must not imply fully healthy |
   | Concrete result, no warnings | Interpretation completed with its lifecycle status and zero-to-many Observations | Preserve Observations, status, IDs, and metadata | Yes | No | According to lifecycle status |
   | Concrete result with warning/limitation | Interpretation completed but reports reduced/unsupported information | Preserve every warning in order; aggregate is warning/limited, not clean success | Yes for current string warning contract | No | Yes for success classification |
   | Concrete `interpret` raises | Invocation failed before a result was returned | Typed `FAILED` result for that interpreter, no Observations, sanitized warning/failure code | Not an exact returned-result mapping; it is boundary failure conversion | Exception type may be retained as a safe code; sensitive message/trace is intentionally omitted | Yes |
   | Unknown future status/result form | Contract evolved without an approved mapping | Static/exhaustiveness failure; if encountered at runtime, typed failure rather than success | No mapping exists | Not silently discarded | Yes |

   Current `ObservationInterpreterResult` has no distinct `partial`, `unsupported`,
   `limited`, or per-call `failed` status and has no structured warning/failure objects.
   Its warning strings are the only current limitation channel. The implementation must
   not invent semantic distinctions that are absent. If a concrete implementation adds
   one of those result forms before this plan is implemented, stop and revise the plan;
   do not flatten it into success or a generic warning.

5. **Validate single-Event result lineage before conversion.** The adapter calls the
   concrete interpreter with the original Event (not a reconstructed Event and not a
   batch dispatcher). Require exactly one `source_production_event_ids` entry equal to
   `event.id`; a missing, additional, or different ID is a typed failed result. Preserve
   the concrete `interpreter_id` and verify it equals the wrapped interpreter's `id`.
   Copy Observations, warnings, and metadata without reordering. Verify each returned
   Observation retains the source Event ID, interpreter ID, Event correlation ID, and
   source references in first-class provenance/context; a lineage violation fails closed
   and returns no observations. Do not overwrite provenance with compatibility metadata.

6. **Define deterministic dispatcher aggregation.** Registration order controls match,
   invocation, `invoked_interpreter_ids`, `interpreter_results`, flattened Observation
   order, and warning order:

   | Scenario | Dispatcher behavior |
   | --- | --- |
   | No interpreter matches | Return zero results; all registered interpreters are declined; expose a typed no-match/unsupported aggregate condition without calling any interpreter. |
   | Exactly one matches | Invoke once and preserve its complete converted result. |
   | Multiple match | Invoke each once in registration order and retain one ordered result per match. Multiple matches are valid fan-out, not ambiguity. |
   | A matching interpreter fails | Record a typed failed result and continue invoking later matches; aggregate cannot be successful. |
   | One succeeds and another warns/is limited | Preserve both results and all warnings in registration/result order; aggregate is completed with warnings/limitations, not clean success. |
   | One succeeds and another fails | Preserve the success and failure independently; aggregate is partial/failed according to an explicit dispatch aggregate status and never clean success. |

   Add an explicit dispatch aggregate status/result classification sufficient to
   distinguish no-match, success, success-with-warnings/limitations, partial failure,
   and total failure. Update `DispatchSummary` to use that classification rather than
   `not warnings`. No exception from one interpreter may erase already obtained results.
   Do not add retries; future durable operation ownership is outside this synchronous
   boundary.

7. **Retain concrete batch compatibility without batch dispatch.** Keep every concrete
   interpreter's current `ProductionEvent | Sequence[ProductionEvent]` API and batch
   contract tests unchanged. The dispatcher sends one Event because current batch
   implementations merely perform deterministic per-Event iteration and no demonstrated
   cross-Event semantic need exists. Existing callers may continue using concrete batch
   APIs directly. If cross-Event interpretation becomes semantically necessary, it
   requires a later plan defining grouping, ordering, replay, and lineage guarantees.

8. **Preserve public compatibility.** `ProductionEventInterpreter` remains a supported
   public compatibility contract, not an internal legacy-only abstraction and not a
   deprecation candidate in this change. Existing imports, construction, subclassing,
   dispatcher registration, and `InterpreterResult` use continue to work. The new
   protocol is additive and structural; callers do not need to inherit from it. Any later
   deprecation requires consumer evidence, compatibility/removal criteria, and separate
   authority.

9. **Document and test the boundary.** Update dispatcher/interpreter READMEs to distinguish
   the structural dispatcher boundary, compatibility adapter, concrete semantics, and
   future durable ingress ordering. Add public exports deliberately; do not reorganize
   concrete packages for naming consistency.

### Reconciliation record

- Changed from the unavailable initial version: cannot be verified textually. This
  authoritative reconstruction adds explicit adapter ownership, minimal protocols,
  exhaustive status/outcome and context mapping tables, fail-closed lineage checks,
  deterministic multi-match/failure aggregation, batch rationale, static-typing rules,
  all-six-interpreter integration coverage, compatibility policy, and durable-ingress
  boundaries.
- Remained unchanged from the request's described recommendation: one narrow adapter,
  one dispatcher, no production implementation in this reconciliation, no broad rename,
  no batch dispatcher without demonstrated semantic need, and preservation of the
  existing public contract.
- Newly discovered conflicts: (1) the referenced initial plan is unavailable; (2) the
  current legacy status enum cannot losslessly represent `unknown`, `configured`,
  `ready`, or `failed`; (3) current dispatch aborts on an interpreter exception and lacks
  aggregate outcome semantics; and (4) stable replay identity is not implemented and
  must not be implied by this compatibility bridge. The approach above resolves (2) and
  (3) additively; (1) remains a documentation-history gap; (4) remains separate runtime
  composition work under ADR-0019.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/production/dispatcher/` | Add protocols, compatibility adapter, aggregate outcome/failure representation, exports, README updates, and protocol-based dispatcher typing. |
| `backend/app/contexts/production/interpreter/interpreter_status.py` | Add concrete lifecycle values required for exact mapping; preserve existing values. |
| `backend/app/contexts/production/interpreter/` | Only compatibility/export/documentation changes proven necessary; retain public contracts. |
| `backend/tests/test_production_dispatcher_contracts.py` | Preserve legacy registration tests and add aggregate/no-match/failure/multi-match behavior. |
| `backend/tests/test_dispatcher_observation_interpreter_compatibility.py` | Add real end-to-end dispatcher coverage for all six concrete interpreters and the adapter boundary. |
| Existing six concrete interpreter contract test modules | Retain direct/batch API tests; change only if an additive compatibility assertion is required. |
| `docs/plans/dispatcher-interpreter-compatibility.md` | Record completion evidence after approved implementation. |

## Data or migration considerations

No schema, persisted data, migration, backup/restore, configuration, or dependency change
is authorized. The bridge preserves an input Production Event's identity; it does not
provide durable ingress identity, replay deduplication, or stable Observation ID reuse.
Future persistence must keep source identity, ingress identity, Production Event ID,
Observation ID, and correlation identity distinct as ADR-0019 requires.

The additive `InterpreterStatus` values change the public enum's accepted value set but
do not alter or remove existing serialized values. No repository persistence or API
currently serializes this enum. If an external consumer is discovered before
implementation, document its forward-compatibility behavior and revise this section.

## Failure and recovery considerations

- Dispatch is synchronous and process-local. It owns no retry, lease, checkpoint, or
  restart recovery.
- One interpreter failure is isolated into an ordered typed result so other matching
  deterministic interpreters still run. Re-dispatch remains the caller's responsibility
  and may create new Observation IDs today; callers must not claim idempotency.
- Contract/lineage mismatches fail closed: no mismatched Observations escape as success.
- Unsupported/no-match and non-interpretable lifecycle states are explicit non-success
  outcomes, never zero-Observation successes.
- A future durable ingress composition must persist and deduplicate before dispatcher
  invocation, record/reuse results atomically or idempotently, and reconcile restart;
  that work requires its own approved plan.
- Registration order is the deterministic tie-breaker. Parallel interpreter execution
  is not introduced because it would complicate stable result ordering and failure
  isolation without demonstrated need.

## Observability requirements

- A dispatch result must reveal the source Production Event ID, dispatcher ID,
  correlation ID, registered/matched/declined counts, ordered invoked interpreter IDs,
  per-interpreter lifecycle/outcome, aggregate outcome, warnings/limitations, and a safe
  failure code.
- Operators/developers must distinguish no match, non-interpretable state, clean success,
  degraded/warning success, partial failure, and total failure.
- Diagnostics must not include Production Event payload/metadata, transcript text, media
  contents, credentials, or raw exception messages. Structured logs/metrics are not
  required by this contract-only correction and cannot substitute for returned state.
- These diagnostics are invocation evidence, not durable operational readiness.

## Test strategy

- Protocol/static tests prove a legacy `ProductionEventInterpreter` and each concrete
  adapter satisfy the dispatcher protocol with no `Any`, cast, ignore, or runtime
  attribute probing.
- Table-driven status tests cover all eight concrete statuses, legacy `experimental`,
  and exhaustiveness. `unknown`, `configured`, `failed`, `disabled`, and `archived`
  cannot be treated as successful or invoked by normal matching; `ready`, `active`, and
  `degraded` retain their distinct meanings.
- Context tests use non-default values and nested metadata to prove exact conversion of
  correlation, timestamp, Recording Block, Stage, and metadata, with no clock call or
  synthesized fact.
- Real dispatcher integration tests instantiate and route supported Events through each
  of Recording Activity, Schedule, Media Artifact, Runtime Clock, Transcript, and Vision
  adapters. For each, assert concrete interpreter ID, source Production Event ID,
  correlation ID, first-class provenance/context source references, status, warning
  order, and Observation order.
- Unsupported Event tests cover wrong type, wrong source, mapping-specific rejection,
  and no-match aggregation without invocation.
- Use a policy/mapping fixture that produces multiple Observations from one Event to
  prove one-to-many preservation, rather than only testing multiple Events.
- Multiple-match tests use two real/adapted matching interpreters or narrowly configured
  concrete instances and prove deterministic registration order.
- Failure tests cover a raising matching interpreter, invalid result source IDs,
  mismatched interpreter ID, missing/wrong Observation provenance, one success plus one
  warning, one success plus one failure, and all matches failing. Assert fail-closed
  results and continued later invocation.
- Warning tests preserve every concrete warning verbatim and in order; summaries must
  not count warning/degraded/failed results as clean success.
- Batch compatibility tests keep each concrete interpreter's direct single/sequence API,
  reject empty batches, preserve Event/Observation ordering, and prove dispatcher calls
  only the single-Event path.
- Public import tests retain all legacy imports and add the intended protocol/adapter
  exports without removing concrete exports.
- Run from `backend`: `uv run pytest` (the compatibility and affected contract suite at
  minimum; full backend suite before completion), `uv run ruff check .`, and
  `uv run pyright`. Run repository-root `git diff --check`. No frontend check is needed
  unless frontend files change.

## Acceptance criteria

- [x] The dispatcher accepts the explicit minimal structural protocol and existing
  `ProductionEventInterpreter` registrations remain source- and runtime-compatible.
- [x] A dispatcher-owned adapter routes supported Events through each of the six real
  concrete Observation Interpreters without `Any`, unsafe casts, `# type: ignore`, or
  runtime duck-typing workarounds.
- [x] The context mapping is field-for-field, does not use implicit time, and synthesizes
  no authoritative fact.
- [x] Every concrete and legacy status/outcome is mapped according to the table; unknown,
  configured, unsupported, warning/limited, degraded, and failed outcomes are never
  reported as clean success.
- [x] No-match, one-match, multi-match, warning, partial-failure, and total-failure
  aggregation are explicit and deterministic.
- [x] One interpreter failure does not erase successful results or prevent later matches
  from running, and lineage/contract violations fail closed.
- [x] Source Production Event ID, correlation, interpreter ID, source references,
  warnings/limitations, one-to-many Observations, provenance, and ordering are preserved.
- [x] Adapter execution never constructs, replaces, or mutates a Production Event and
  does not conflate source, ingress, Event, or Observation identity.
- [x] Concrete batch APIs and tests remain supported; no batch dispatcher is introduced.
- [x] Public import compatibility is proven and `ProductionEventInterpreter` is neither
  removed nor deprecated.
- [x] All specified tests, Ruff, Pyright, and `git diff --check` pass, and completion
  evidence records only commands actually run.
- [x] Documentation stated at this plan's completion baseline that durable/restart-safe
  ingress and replay-stable downstream effects were unimplemented and required before
  runtime composition. Stable ingress was added later under its own plan; downstream
  durable effects and runtime composition remain unimplemented.

## Rollback or reversal

Before persistence or runtime composition, reverse the additive dispatcher protocol,
adapter, status values, aggregation contracts, exports, tests, and documentation as one
bounded code change. Existing legacy `ProductionEventInterpreter` behavior remains the
fallback because this plan does not remove it. No data, schema, dependency,
configuration, or external side effect requires reversal.

If callers adopt new aggregate/status values, retain compatibility aliases or stage a
separate deprecation rather than removing values during rollback. Never roll back by
bypassing the dispatcher or duplicating it for concrete interpreters.

## Open questions

- Documentation-history gap: where is the initial plan named by the reconciliation
  request? It is absent from the synchronized checkout and visible Git history. This does
  not block review of this reconstructed plan but prevents a verified textual change log.
- Durable ingress sequencing: this bounded compatibility implementation may proceed
  after approval, but no continuous watcher/recorder/provider runtime may compose it
  until ADR-0019's durable ingress identity and replay work has its own approved plan and
  implementation.
- Public consumers: repository evidence shows public exports/tests but no external
  consumers. If external consumers of serialized `InterpreterStatus` or exact
  `DispatchResult` construction are identified, their compatibility requirements must
  be added before implementation.

## Completion record

- Approval and review history: the plan was originally implemented while still marked
  `Proposed`. The user explicitly approved this bounded plan on 2026-08-07 and directed
  correction of independent-review findings DIC-001 through DIC-004. This record now
  distinguishes proposal, approval, implementation, independent review, correction,
  and acceptance. A second independent re-review returned `CORRECT BEFORE ACCEPTANCE`
  with Medium findings DIC-RR-001 and DIC-RR-002. Their final hardening correction is
  complete. DIC-RR-003 then corrected clean-success summary counting, and a fresh
  independent re-review accepted the completed boundary with no remaining findings.

- Implemented revision: 2026-08-07. Added the minimal structural
  `DispatcherInterpreter` protocol, dispatcher-owned `ObservationInterpreterAdapter`,
  additive legacy status values, explicit aggregate `DispatchStatus`, deterministic
  registration-order fan-out, fail-closed lineage validation, and sanitized exception
  isolation. The adapter invokes the existing single-Event form of each concrete batch
  API and does not construct or mutate the Event.
- Files actually changed: dispatcher protocol, compatibility package, dispatch status,
  dispatcher/result/summary/exports and README; legacy interpreter status and eligible
  status set; Observation Interpreter lineage extraction, exports, and README;
  dispatcher, interpreter-status, Observation context/provenance, all-six concrete
  compatibility tests and their reusable test fixture aliases; this completion record
  and the plan index. No schemas, migrations, dependencies, production configuration,
  frontend files, persistence, or runtime composition changed.
- Behavioral changes: `ProductionEventDispatcher` accepts structural participants;
  invokes all matches in registration order; retains ordered per-interpreter results and
  flattened Observations; converts an exception into a typed `FAILED` result and
  continues; and classifies no-match, success, warning/degraded success, partial failure,
  and total failure explicitly. Legacy `ProductionEventInterpreter` construction,
  subclassing, imports, interpretation, and result preservation remain supported.
- Status compatibility: concrete `UNKNOWN`, `CONFIGURED`, `READY`, `ACTIVE`,
  `DEGRADED`, `FAILED`, `DISABLED`, and `ARCHIVED` map explicitly to same-valued legacy
  statuses. Existing legacy string values remain unchanged; `EXPERIMENTAL` remains a
  legacy-only supported value. Warning-bearing and degraded results aggregate as
  `SUCCESS_WITH_WARNINGS`. `UNKNOWN`, `CONFIGURED`, `FAILED`, `DISABLED`, and
  `ARCHIVED` are non-interpretable failures whose Observations do not survive.
  `READY` and `ACTIVE` are clean successes; `DEGRADED` and legacy `EXPERIMENTAL` are
  successful with warning/degraded aggregate semantics. Unsupported future statuses
  become a typed failure. Aggregate precedence is no results -> `NO_MATCH`; failures
  without success -> `TOTAL_FAILURE`; mixed failure and success -> `PARTIAL_FAILURE`;
  otherwise any warning/degraded/experimental condition -> `SUCCESS_WITH_WARNINGS`;
  otherwise -> `SUCCESS`.
- Corrective lineage validation: the adapter now validates result source Event ID and
  interpreter ID; each Observation's required provenance; source Event ID, type, and
  occurrence time; interpreter ID; Observation and context correlation IDs; Event-derived
  Stage, Recording Block, scheduled activity, transcript stream, media artifact, and
  timeline references when present; and source producer identifier. Validation is
  atomic per adapter result: one malformed member rejects the entire one-to-many result,
  releases no Observations, and yields a sanitized typed failure while later matching
  interpreters continue.
- DIC-RR-001 final hardening: selected aggregate-output filtering (Option B) as the
  least disruptive fail-closed strategy. `DispatchResult.observations` now consults the
  same centralized status classification used by dispatcher sanitization, aggregate
  status, and summary counting. Direct construction therefore preserves raw
  per-interpreter diagnostic results without releasing Observations for `UNKNOWN`,
  `CONFIGURED`, `FAILED`, `DISABLED`, `ARCHIVED`, or unsupported/future statuses.
  `READY` and `ACTIVE` survive as clean success; `DEGRADED` and legacy `EXPERIMENTAL`
  survive with warning aggregate semantics. Unsupported/future values classify as
  fail-closed aggregate failures and cannot release Observations.
- DIC-RR-002 final hardening: the centralized Event lineage extractor now returns an
  explicit state for every Stage, Recording Block, scheduled activity, transcript
  stream, media artifact, timeline, and producer identifier: `ABSENT`, `VALID`,
  `MALFORMED`, or `CONTRADICTORY`. It evaluates all permitted structured and typed
  reference candidates. Multiple equivalent candidates are accepted. Any malformed
  candidate fails even when another candidate is valid, and disagreeing valid
  candidates fail without precedence. Dispatcher-context Stage and Recording Block
  fallback is allowed only for `ABSENT`; it never replaces malformed or contradictory
  Event data. The adapter converts invalid extraction into a sanitized typed failure
  before invoking the concrete interpreter, and dispatcher fan-out continues.
- Tests added or updated: real dispatcher integration for Recording Activity, Schedule,
  Media Artifact, Runtime Clock, Transcript, and Vision interpreters; exact context and
  exhaustive status mapping; unsupported/no-match; deterministic multiple-match order;
  warning/degraded aggregation; partial and total failure; exception sanitization and
  later-match continuation; public enum values and existing dispatcher behavior. The
  correction adds table-driven coverage of every concrete status, legacy experimental,
  unsupported future status, every newly enforced provenance field, missing provenance,
  malformed one-to-many atomicity, adapter exception isolation, and later-adapter output
  preservation.
- Final-hardening tests: direct `DispatchResult` construction covers every supported
  status and an unsupported future value; malformed structured values cover all seven
  lineage categories; Stage and Recording Block cover absent-only context fallback and
  malformed/contradictory fallback protection; reference tests cover structured/reference
  conflicts, conflicting and equivalent duplicates, and malformed/valid candidates in
  both orders. Additional tests prove sanitized total failure, atomic partial failure,
  later-match continuation, and surviving later-adapter output. Two legacy fixtures that
  intentionally encoded precedence conflicts were corrected to use equivalent
  representations, consistent with their real Event builders.
- DIC-RR-003 independent-review correction: `DispatchSummary` now uses the centralized
  status warning semantics when counting clean successes. Warning-bearing active,
  degraded, and legacy experimental outcomes are never counted as clean success. The
  corrected 99-test focused suite and scoped strict Pyright both pass, and a fresh
  independent re-review recommends acceptance with no remaining findings.
- Validation commands and results:
  - `uv run pytest tests/test_dispatcher_observation_interpreter_compatibility.py tests/test_production_dispatcher_contracts.py tests/test_production_interpreter_contracts.py -q` — passed (73 tests).
  - `uv run pytest -q` — compatibility changes passed, but the final full command ended
    with five unrelated Windows-environment failures: three symlink privilege failures
    and two POSIX-path assertions evaluated with Windows path rules.
  - `uv run pytest -q --ignore=tests/test_local_filesystem_discovery_bounds_and_security.py --ignore=tests/test_local_filesystem_discovery_contracts.py` — passed (all remaining backend tests; one existing FastAPI/httpx deprecation warning).
  - `uv run ruff check .` — passed.
  - `uv run pyright` — failed only on two pre-existing Windows typing errors for
    `os.mkfifo` in `test_local_filesystem_discovery_bounds_and_security.py`.
  - `uv run pyright app/contexts/production/dispatcher app/contexts/production/interpreter tests/test_dispatcher_observation_interpreter_compatibility.py tests/test_production_dispatcher_contracts.py tests/test_production_interpreter_contracts.py tests/test_recording_activity_observation_interpreter_contracts.py tests/test_schedule_observation_interpreter_contracts.py tests/test_media_artifact_observation_interpreter_contracts.py tests/test_runtime_clock_observation_interpreter_contracts.py tests/test_transcript_observation_interpreter_contracts.py tests/test_vision_observation_interpreter_contracts.py` — passed with zero errors or warnings.
  - `git diff --check` — passed; Git emitted only expected LF-to-CRLF working-copy warnings.
- Final-hardening validation commands and results:
  - `uv run pytest tests/test_dispatcher_observation_interpreter_compatibility.py tests/test_production_dispatcher_contracts.py tests/test_production_interpreter_contracts.py tests/test_recording_activity_observation_interpreter_contracts.py tests/test_schedule_observation_interpreter_contracts.py tests/test_media_artifact_observation_interpreter_contracts.py tests/test_runtime_clock_observation_interpreter_contracts.py tests/test_transcript_observation_interpreter_contracts.py tests/test_vision_observation_interpreter_contracts.py -q` — passed (215 tests).
  - `uv run pytest -q` — compatibility changes passed; the command retained exactly five
    known Windows filesystem failures: three `WinError 1314` symlink privilege failures
    and two POSIX-path expectation failures where Windows classified `/recordings/...`
    as non-absolute.
  - `uv run pytest -q --ignore=tests/test_local_filesystem_discovery_bounds_and_security.py --ignore=tests/test_local_filesystem_discovery_contracts.py` — passed all remaining
    backend tests with one existing Starlette/httpx deprecation warning.
  - `uv run ruff check .` — passed.
  - `uv run pyright` — retained exactly two known Windows errors at
    `test_local_filesystem_discovery_bounds_and_security.py:176`: unknown type for
    `os.mkfifo` and `os.mkfifo` not being a known `os` attribute.
  - `uv run pyright app/contexts/production/dispatcher app/contexts/production/interpreter app/contexts/production/observation_interpreter tests/test_dispatcher_observation_interpreter_compatibility.py tests/test_observation_context_provenance_contracts.py tests/test_production_dispatcher_contracts.py tests/test_production_interpreter_contracts.py tests/test_recording_activity_observation_interpreter_contracts.py tests/test_schedule_observation_interpreter_contracts.py tests/test_media_artifact_observation_interpreter_contracts.py tests/test_runtime_clock_observation_interpreter_contracts.py tests/test_transcript_observation_interpreter_contracts.py tests/test_vision_observation_interpreter_contracts.py` — passed with zero errors or warnings.
  - `git diff --check` — passed; Git emitted only expected LF-to-CRLF working-copy
    warnings.
- Acceptance evidence: the implementation and all three final-hardening findings are
  covered by focused behavior tests and scoped strict Pyright; fresh independent Codex
  review recommends acceptance. Subsequent filesystem test-portability correction also
  makes the full backend pytest and Pyright matrix pass on Windows.
- Deviations: no architectural deviation. Reusable public aliases were added to the six
  existing test modules so strict Pyright can share their real builders without private
  imports. The runtime-clock and context-provenance fixtures were corrected from
  contradictory precedence examples to equivalent representations because DIC-RR-002
  expressly rejects arbitrary precedence. No production concrete interpreter API
  changed.
- Remaining risks and deliberately excluded follow-up: durable ingress identity,
  replay-stable Observation identity, persistence, retry/recovery, filesystem discovery,
  and runtime composition remain unimplemented. External callers that supplied
  contradictory lineage and relied on first-match precedence will now receive the
  intended fail-closed behavior; repository evidence identifies no such valid consumer.
  Filesystem portability is tracked and completed by the separate ABR-007 plan.

### Contract Stabilization follow-up (CSR-003 through CSR-005)

- `DispatchResult` now canonicalizes top-level and per-result warning occurrences before
  aggregation. Any visible warning produces `SUCCESS_WITH_WARNINGS` unless failure
  precedence produces `PARTIAL_FAILURE` or `TOTAL_FAILURE`; top-level diagnostics can no
  longer produce false clean success.
- A `can_interpret` exception becomes an ordered `InterpreterSupportFailure` with a
  sanitized failure code and warning. It is not counted as a normal decline, and later
  registrations are still evaluated. The exception catch remains scoped to the
  interpreter support boundary.
- Focused tests cover direct top-level warnings, derived warnings, sanitized predicate
  exceptions, later-match continuation, and aggregate precedence. The acceptance
  checklist above is reconciled against implementation and independent-review evidence.
- Durable ingress and timestamp changes remain owned by their separate plans; this
  follow-up did not compose a runtime or broaden dispatcher responsibility.
- Final closure validation passed the full 1,578-test backend suite with six documented
  skips, Ruff, Pyright, the frontend build/lint/typecheck matrix, and `git diff --check`.
  Exact current evidence is recorded in the
  [Contract Stabilization correction status](../reviews/contract-stabilization-correction-status.md).
