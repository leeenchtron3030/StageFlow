# API route code-quality residue cleanup

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: ED-0062 and the explicit 2026-08-21 implementation request.
- Implementation-ready: Yes
- Required escalation or approval, if any: None.

## Related findings or ADRs

- Finding/disposition: Due-diligence API code-quality and immutability residue.
- ADR: None required.
- Engineering Directive: ED-0062.

## Problem statement and verified behavior

Recent API projections contain shallowly frozen response models with mutable nested dictionaries, duplicated Program and Kernel fallback construction, and three converters that weaken parameters to `object`, import domain types locally, and recover type safety with assertions.

## Desired behavior and scope

Make nested mapping values recursively immutable in Python while preserving JSON objects, centralize API-local response mapping at the smallest boundary, and use normal imports with real domain parameter types. Route paths, fields, values, status codes, domain authority, and pagination remain unchanged.

## Implementation approach and affected files

Add an API-local response helper module, update `demo.py`, `kernel_status.py`, and `media_timing_evidence.py`, and extend relevant API tests. Domain contexts remain independent of FastAPI/Pydantic. No data, schema, migration, runtime configuration, or recovery effect exists.

## Test strategy and acceptance criteria

- Nested response mappings reject mutation.
- The three local-import-plus-assert converter patterns are removed without `Any`, casts, or replacement assertions.
- Duplicated Program/fallback construction is centralized.
- Existing representative JSON payloads and status codes are unchanged.
- Full backend pytest, Ruff, and Pyright pass.

## Rollback or reversal

Revert the helper, call sites, and tests together.

## Open questions

None.

## Completion record

Implemented 2026-08-21.

- Added API-local recursively immutable mapping types that retain JSON-object serialization.
- Centralized Program change mapping and Kernel fallback response construction.
- Removed all three local-import-plus-assert converters and the remaining Kernel type assert
  by using precise domain parameter types and explicit narrowing.
- New immutability tests and existing API tests passed in the full backend suite; Ruff and
  Pyright passed. External route paths, fields, status codes, and authority are unchanged.
