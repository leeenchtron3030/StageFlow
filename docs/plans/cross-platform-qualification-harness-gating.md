# Cross-platform qualification harness gating

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: ED-0060 and the explicit 2026-08-21 implementation request.
- Implementation-ready: Yes
- Required escalation or approval, if any: None.

## Related findings or ADRs

- Finding/disposition: Due-diligence cross-platform tooling residue.
- ADR: None required.
- Engineering Directive: ED-0060.

## Problem statement and verified behavior

The Razer harness imports on Linux, but its endurance path raises `OSError` when the Windows process-memory API is unavailable. Its CLI has no platform gate or skip result.

## Desired behavior and scope

On non-Windows platforms, the endurance command returns a bounded JSON-compatible `skipped` result with reason `unsupported_platform` before configuration, PostgreSQL, or media access. Windows behavior and every other command remain unchanged. Porting memory sampling or claiming Linux qualification is out of scope.

## Implementation approach and affected files

Add a small platform predicate/wrapper in `backend/tests/qualification/durable_kernel_razer.py`, route only the endurance CLI command through it, and add `backend/tests/test_durable_kernel_razer.py` with injected-platform behavior tests. No data or migration effect exists.

## Test strategy and acceptance criteria

- Non-Windows endurance returns the typed skip without Windows API access.
- Windows endurance delegates unchanged.
- Full backend pytest, Ruff, and Pyright pass.

## Rollback or reversal

Revert the wrapper and tests.

## Open questions

None.

## Completion record

Implemented 2026-08-21.

- Added an explicit platform wrapper that writes a typed `unsupported_platform` skip on
  non-Windows hosts before entering the Windows endurance implementation.
- Unit tests cover non-Windows skip and Windows delegation; the full backend suite passed.
- No production code, deployment, or qualification semantics changed on Windows.
