# Recursive metadata immutability

## Status

Completed — independent review accepted

## Execution authority

- Classification: Green autonomous
- Authority evidence: accepted ABR-006 and Phase-2 disposition.
- Implementation-ready: Yes
- Required escalation or approval, if any: None while evidence-backed domain values remain
  compatible and public field names/signatures do not change.

## Problem statement

Legacy frozen contracts copy and proxy only the top-level metadata mapping. Nested caller
maps, lists, and sets remain mutable, so retained domain facts and policy inputs can
change without a new event/revision.

## Intended outcome

One neutral shared helper recursively snapshots metadata mappings and converts nested
mutable containers to immutable equivalents. Accepted values are JSON-compatible
scalars/containers plus evidence-backed immutable StageFlow identifiers, enums, aware
datetimes, and already-frozen StageFlow value contracts. Unsupported mutable/active
objects fail closed. Identity, provenance, and behavior-driving facts remain first-class.

## Scope

- Add the shared freezer without a serialization framework or dependency.
- Apply it to legacy domain, ingress, reasoning, policy/result, acceptance, repository,
  dispatcher/interpreter, and adapter metadata boundaries that currently shallow-freeze.
- Preserve existing newer JSON-only boundary helpers and their stricter security rules.
- Add cross-boundary mutation, accepted-domain-value, and unsupported-object tests.
- Update current contract documentation.

## Non-goals

- Moving authoritative facts into or out of metadata, broad renames, schema/persistence,
  generic object serialization, or unrelated container refactors.

## Compatibility and rollback

Mapping reads and equality remain compatible; nested mappings become read-only and
lists/sets become tuple/frozenset snapshots. Existing evidenced immutable domain values
remain accepted. Unsupported mutable object metadata now raises a typed `ValueError`, as
authorized by ABR-006's accepted-type requirement. Rollback is an isolated helper/use-site
revert; no data migration exists.

## Validation

- New focused recursive metadata invariant suite.
- Affected existing contract/behavior suites.
- Full backend pytest, Ruff, and Pyright.
- `git diff --check` and independent review.

## Completion record

- Files and migrations actually changed: added `backend/app/shared/metadata.py`, replaced
  all 124 legacy shallow metadata freezes across Production and shared contracts, added
  `backend/tests/test_recursive_metadata_immutability.py`, and updated directly affected
  contract/architecture documentation. No schema, migration, dependency, or runtime
  configuration changed.
- Commands and tests actually run: focused recursive-metadata and representative
  contract suites; scoped Ruff and strict Pyright; full `uv run pytest`,
  `uv run ruff check .`, and `uv run pyright`; `git diff --check`.
- Results and warnings: focused independent-review validation passed 160 tests with
  Ruff and Pyright clean. The final full backend matrix passed 1,543 tests with 5
  expected platform skips and one existing Starlette/httpx deprecation warning; Ruff
  and Pyright passed. `git diff --check` found no whitespace errors and reported only
  working-copy LF-to-CRLF conversion warnings.
- Execution authority used: Green autonomous.
- Approved deviations: None.
- Rollback status: Not needed.
- Independent review: accepted after corrections for cycles, non-finite floats,
  unbounded external enums, and strict typing. No actionable finding remains.
- Remaining work: no completion blocker. An explicit nesting-depth bound and broader
  per-boundary integration sampling remain non-blocking hardening opportunities before
  externally supplied or durable metadata expands.
