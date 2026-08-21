# Media candidate collection coordinator failure visibility

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: Acquisition-style due-diligence audit (2026-08-20, commit `42e71c2`),
  Major finding "The busiest file in the codebase is unrefactored, and its failures are
  invisible"; explicit 2026-08-21 user directive to proceed with structural fortification.
- Implementation-ready: Yes
- Required escalation or approval, if any: None. This plan is deliberately scoped to
  failure-visibility only (observability), not a structural refactor — see Out of scope.

## Related findings or ADRs

- Finding/disposition: Due-diligence audit Major finding —
  `backend/app/contexts/production/media_collection/media_candidate_collection_coordinator.py:266,622`
  (bare `except Exception:` with no re-raise and no logging call), and
  `backend/app/core/lifecycle/lifespan.py:23-33` (startup errors stashed only in
  `app.state`, never logged) — combined with `logging.basicConfig` being configured
  somewhere in the tree but never actually invoked anywhere in the backend.
- ADR: None required — no behavior or authority change, purely observability.
- Engineering Directive: ED-0057.

## Problem statement

`media_candidate_collection_coordinator.py` has grown to 2,072 lines and 43 methods with
broad exception handling that swallows failures silently. A broken Postgres connection at
boot currently produces zero log output — an operator must know to poll a status endpoint
to discover a problem exists at all. This is a real operational risk during a live,
time-boxed event where nobody will be polling a status endpoint proactively.

## Verified current behavior

- Bare `except Exception:` blocks at the cited line numbers catch and discard errors
  without logging or re-raising.
- `logging.basicConfig(...)` exists in the codebase but no `logging.getLogger(...).info/
  warning/error(...)` call is ever actually invoked in the backend, including the startup
  path.
- `lifespan.py:23-33` stores startup failures only in `app.state`, with no log line marking
  that a failure occurred.

## Desired behavior

Every caught exception in the coordinator's broad handlers is logged with enough context
(operation, candidate/asset identity where available, exception type and message) before
being handled or swallowed. Startup failures produce an actual log line, not just an
`app.state` write. No behavior, retry policy, or return value changes — this is strictly
additive observability.

## In scope

- Replace bare `except Exception:` blocks at the cited locations (and any other
  same-pattern blocks discovered in the same file during implementation) with either: (a)
  a narrower, already-anticipated exception type where one is discoverable from context,
  logged and handled exactly as today, or (b) the same broad catch, but with a logging
  call added before the existing swallow/continue behavior. Do not change which exceptions
  are caught or what happens after logging unless the existing behavior is itself
  provably wrong (in which case: stop and report, do not silently fix a second thing here).
- Wire an actual `logging.getLogger(__name__)` call at the startup failure path in
  `lifespan.py` so a failure is visible in process output, not only in `app.state`.
- Confirm `logging.basicConfig` (or equivalent handler/formatter setup) actually takes
  effect for these new log calls — if it doesn't currently wire to anything real, fix the
  minimum needed for these calls to reach stdout/stderr or the existing log sink.
- Tests proving a caught-and-logged exception actually produces a log record (using
  `caplog` or equivalent), without asserting on exact wording that would make the test
  brittle.

## Out of scope

- Decomposing or refactoring the 2,072-line coordinator's structure, method count, or
  responsibilities — that is real, separately worthwhile work, explicitly flagged by the
  audit itself as "not deal-blocking... ordinary post-close backlog," and belongs in its
  own plan with its own review, not bundled into an observability-only change.
- Changing retry policy, error classification, or any return value/control flow beyond
  adding a log call before existing behavior.
- Any change to Session, media, association, or package authority.

## Constraints

- Architecture and terminology constraints: purely additive observability; must not
  introduce a new authority-relevant side effect.
- Security and data-handling constraints: log messages must not include DSNs, credentials,
  full media paths, or transcript content — presence/identity references only, consistent
  with the project's existing sanitized-projection conventions.

## Implementation approach

1. Locate every bare/broad exception handler in
   `media_candidate_collection_coordinator.py` (starting from the two cited line numbers,
   confirming whether the file has moved since the audit's commit).
2. For each, add a logging call carrying operation name, relevant identity (candidate/asset
   ID, not path), and the exception's type/message, before the existing handling continues
   unchanged.
3. In `lifespan.py`, add a logging call at the startup-failure path alongside the existing
   `app.state` write.
4. Confirm the logging configuration actually delivers these records somewhere real (fix
   the minimal wiring gap if `logging.basicConfig` isn't currently effective).
5. Add or extend tests asserting a log record is produced when the relevant exception path
   is exercised.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/production/media_collection/media_candidate_collection_coordinator.py` | Add logging calls to existing broad exception handlers |
| `backend/app/core/lifecycle/lifespan.py` | Add logging call at startup-failure path |
| Backend logging configuration (wherever `logging.basicConfig` currently lives) | Confirm/fix effective wiring if not already reaching a real sink |
| Relevant test file(s) under `backend/tests/` | Assert a log record is produced on the exercised failure path |

## Data or migration considerations

None.

## Failure and recovery considerations

No change to failure/recovery behavior itself — only its visibility. Explicitly do not use
this plan to change what is retried, what fails the operation, or what is surfaced to the
Producer UI.

## Observability requirements

A broken Postgres connection (or other currently-silent failure) at boot or during a
coordination cycle must now produce a log line an operator watching process output would
see, without needing to poll a status endpoint.

## Test strategy

- Unit test(s) exercising at least one of the previously-silent exception paths, asserting
  a log record is emitted with the expected logger name and severity (not exact message
  text).
- Full backend quality commands: `uv run pytest`, `uv run ruff check .`, `uv run pyright`.

## Acceptance criteria

- [ ] Every previously bare/silent exception handler identified in scope now logs before
  continuing with its existing (unchanged) behavior.
- [ ] Startup failures produce a real log line in addition to the existing `app.state`
  write.
- [ ] No return value, retry policy, or control flow changed anywhere in this change.
- [ ] No DSN, credential, full media path, or transcript content appears in any new log
  call.
- [ ] At least one test proves a log record is actually produced on a previously-silent
  path.

## Rollback or reversal

Revert the added logging calls and any minimal logging-configuration fix. No data or
behavior change to reverse.

## Open questions

- Confirm current line numbers/method boundaries in the coordinator file, since the audit
  was run against an earlier commit (`42e71c2`) and the file may have moved since.

## Completion record

Implemented 2026-08-21.

- Added ERROR records to every broad coordinator handler and both lifespan startup
  failure paths while preserving existing return values and control flow.
- Logs contain bounded operation/identity fields and exception type only. Raw exception
  messages were deliberately omitted because they can contain paths or connection data;
  this is a security-preserving deviation from the initial approach text.
- Caplog coverage passed in the full 1,796-pass backend suite; Ruff and Pyright passed.
- Existing `configure_logging()`/`logging.basicConfig()` wiring remains the process sink.
