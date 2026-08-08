# Production timestamp invariants

## Status

Completed

## Execution authority

- Classification: Explicit approval granted; remaining implementation is Green within
  the approved breaking transition.
- Authority evidence: ADR-0021, accepted ABR-005, approved D-07, and the user-approved
  strict aware-time transition dated 2026-08-07.
- Implementation-ready: Yes.
- Required escalation or approval, if any: None while semantic timestamp meanings remain
  distinct and no new normalization authority is invented.

## Problem and inventory

Legacy Event, Observation, Evidence, Evaluation, Operational State, adapter, policy,
timeline, and context contracts contain 27 implicit `datetime.now(UTC)` calls outside
the shared Clock boundary. Naive timestamps are accepted and two compatibility parsers
silently attach UTC.

The affected implicit-time groups are:

- shared `DomainEvent`;
- Production Event receipt;
- dispatcher and both interpreter contexts;
- Observation, EvidenceSet, Hypothesis, Finding, VerificationDecision;
- OperationalProduct, OperationalState, TransitionEvaluation;
- Timeline RecordingBlock/SessionWindow and SessionWindowProduct;
- recording/session transition policy evaluation defaults;
- recording, media, schedule, runtime-clock, transcript, vision, and operator Event
  conversion receipt defaults; and
- two metadata timestamp parsers in Session boundary/transition logic.

Newer ED-0046 through ED-0053 contracts already implement the preferred aware and
semantically distinct pattern and must remain intact.

## Approved transition

This is an intentional breaking internal transition before operational runtime, durable
schemas, or external consumers depend on the legacy behavior:

- domain/request timestamps become required explicit parameters;
- externally supplied values reject naive datetimes;
- source-specific normalization is allowed only in a future explicitly configured source
  adapter policy, not in generic domain helpers;
- infrastructure callers obtain current time from the existing `Clock` boundary and pass
  it explicitly;
- UTC normalization is available for persistence/canonicalization but never invents a
  missing timezone; and
- source occurrence, receipt, observation, evaluation, acceptance, attempt, commit, and
  organizational-anchor times remain distinct.

## Implementation approach

1. Add small shared `require_aware_datetime` and `normalize_utc_datetime` helpers under
   `app.shared.time`; make `FixedClock` reject naive configured values.
2. Remove legacy default factories and optional receipt/evaluation fallbacks. Reorder
   dataclass fields only where Python requires non-default fields before default fields;
   preserve field names and valid aware values.
3. Validate every affected timestamp in `__post_init__` or method entry before comparison,
   ordering, ID derivation, or persistence.
4. Replace both silent `replace(tzinfo=UTC)` parsers with fail-closed parsing that accepts
   only aware strings.
5. Update callers/tests to supply explicit aware values. Infrastructure examples/tests
   use `FixedClock` or an explicit aware timestamp.
6. Add focused table-driven tests for naive rejection, non-UTC offsets, DST-fold-aware
   values, backward clocks where ordering rules apply, canonical UTC normalization,
   semantic-time separation, and replay with a different current Clock.

## Scope and non-goals

In scope are the identified legacy Production/shared contracts, their direct callers and
tests, shared time validation, and affected documentation. No generic scheduling/timezone
framework, source timezone configuration, persistence serialization, runtime composition,
or new clock service is introduced.

## Compatibility and rollback

Valid timezone-aware values retain their datetime representation and comparison behavior.
Calls that omit an authoritative timestamp or pass a naive value now fail at construction
or call binding by design. Rollback before durable use is a code/test revert; once durable
schemas depend on strict time, rollback to ambiguity is prohibited.

## Validation

- Focused timestamp invariant and affected adapter/policy tests.
- Existing time, Event, Observation, Evidence, Operational State, acceptance/repository,
  dispatcher/interpreter, and timeline suites.
- Full backend pytest, Ruff, and Pyright.
- `git diff --check` and fresh independent verification.

## Acceptance criteria

- [x] All inventoried external/domain timestamps reject naive values absent explicit
  source normalization authority.
- [x] Domain/request times are explicit; infrastructure-created current time enters
  through `Clock` and no legacy domain wall-clock calls remain.
- [x] No silent UTC attachment remains.
- [x] Source, receipt, observation, evaluation, acceptance, attempt, commit, and anchor
  meanings remain distinct.
- [x] Valid aware non-UTC values remain accepted and UTC normalization preserves the
  instant.
- [x] Mixed aware/naive comparisons cannot escape validation.
- [x] Tests cover offset/DST, backward-clock rules, round-trip/canonicalization, and replay
  with a different Clock.

## Completion record

- Added shared aware validation, aware-only parsing, and canonical UTC normalization;
  `FixedClock` now rejects ambiguous values.
- Removed all 27 inventoried implicit wall-clock defaults/fallbacks and made affected
  domain/request times explicit. `SystemClock` is the sole production reader of
  `datetime.now`.
- Extended validation to directly affected authoritative carriers including Event and
  Observation provenance/location, Evidence and transition anchors, TimeBoundary, and
  acceptance request/result/supersession/summary values.
- Both legacy metadata parsers now return no timestamp for naive input. No production
  `replace(tzinfo=UTC)` remains.
- Schedule Event occurrence and receipt are now separate explicit inputs. PostgreSQL
  ingress preserves occurrence, first receipt, last receipt, and migration application
  time separately.
- Tests cover omitted-default contract shape, naive rejection, non-UTC offsets, a DST
  fold, canonical UTC, backward injected clocks, replay identity, and parser fail-closed
  behavior. Full validation evidence is recorded in the Contract Stabilization
  correction status report.
- This is the approved deliberate internal compatibility break. No compatibility wrapper
  or source-timezone authority was invented.
