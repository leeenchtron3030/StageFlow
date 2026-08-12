# Local filesystem discovery race hardening

## Status

Completed — independent review accepted

## Execution authority

- Classification: Green autonomous
- Authority evidence: accepted ABR-007 in the architecture-baseline disposition;
  ED-0053's implemented shallow, bounded, read-only adapter scope.
- Implementation-ready: Yes
- Required escalation or approval, if any: None.

## Related findings or ADRs

- Finding/disposition: ABR-007 — accepted with qualification.
- ADR: None required by the accepted review/disposition.
- Engineering Directive: ED-0053.

## Problem statement

The configured target is validated with `lstat`, enumerated later by pathname, and its
children are inspected through further pathname lookups. Replacing the directory between
those operations can cause StageFlow to inspect a different filesystem object than the
one that passed validation.

## Current behavior verified

- Discovery is synchronous, stateless, shallow, bounded, read-only, and rejects known
  target/ancestor/child symlinks.
- Target validation, enumeration, and child inspection are separate path operations.
- No target-identity revalidation occurs before candidates are returned.
- Existing filesystem tests contain Windows portability defects that prevent the full
  configured backend matrix from passing on the current development host.

## Intended outcome

Directory discovery captures the validated target identity. On platforms with
descriptor-relative directory support, it binds enumeration and child inspection to an
opened no-follow directory descriptor and also revalidates the pathname. Other
platforms use pathname enumeration with identity revalidation after enumeration and
after child inspection. If the target disappears, becomes a symlink/non-directory,
becomes inaccessible, or has a different stable object identity, the operation fails
closed and returns no candidates with a typed reason. Later content access remains
independently unauthorized by discovery.

## Scope

- Add typed target-change reporting.
- Bind directory inspection to a validated descriptor where supported and revalidate
  target identity at the race-sensitive boundaries on every platform.
- Add deterministic replacement fault coverage without requiring symlink privilege.
- Preserve the Linux symlink/FIFO tests while making them portable on Windows.
- Document operating-system/filesystem identity limitations and the unchanged authority
  boundary.

## Non-goals

- Recursive discovery, watching, polling, content reads, readiness evaluation, or asset
  registration.
- Granting future processing authority or solving later file-open races.
- New dependencies, persistence, services, or runtime composition.

## Compatibility and failure behavior

- Existing successful results and ordering remain unchanged when the target identity is
  stable.
- Target replacement becomes a typed blocked result containing no candidates.
- Filesystems without a meaningful device/object identifier receive only the documented
  type/symlink revalidation guarantee; discovery does not claim stronger identity safety.

## Implementation sequence

1. Add typed target-change reason/limitation values.
2. Add descriptor-relative binding where supported plus target revalidation after
   enumeration and child inspection.
3. Add replacement, disappearance, and stable-target behavior tests.
4. Correct platform-only test assumptions without reducing Linux coverage.
5. Update package and lifecycle documentation.
6. Run focused and repository-wide validation and review the diff.

## Validation

- Focused local-filesystem discovery tests.
- Full backend pytest, Ruff, and Pyright.
- Frontend build/lint/typecheck because the phase ends with the full matrix.
- `git diff --check`.

## Rollback

Revert the isolated code, enum, tests, and documentation change. No data, schema,
dependency, or runtime-configuration rollback is required.

## Completion record

- Files and migrations actually changed: updated the local-filesystem adapter, typed
  reason/limitation vocabulary, security/contract/architecture tests, package guide,
  lifecycle architecture guide, and this plan. No schema, migration, dependency, or
  runtime configuration changed.
- Commands and tests actually run: focused filesystem pytest, Ruff, and scoped strict
  Pyright; full `uv run pytest`, `uv run ruff check .`, and `uv run pyright`;
  `git diff --check`.
- Results and warnings: the final focused run passed 53 tests with 5 expected Windows
  platform/privilege skips; Ruff and Pyright passed. The full backend matrix passed
  1,543 tests with the same 5 skips and one existing Starlette/httpx deprecation
  warning; Ruff and Pyright passed. `git diff --check` found no whitespace errors and
  reported only working-copy LF-to-CRLF conversion warnings.
- Execution authority used: Green autonomous.
- Approved deviations: None.
- Rollback status: Not needed.
- Independent review: accepted after descriptor-relative binding, real replacement
  fault tests, narrowed portability skips, and explicit POSIX/fallback test routing.
- Remaining work: no completion blocker. Pathname fallback cannot eliminate a transient
  swap-and-restore between checkpoints, and filesystems with weak object identities
  retain the documented limitation.
