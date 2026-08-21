# Minimal shared-secret authentication for the Demo/Event-Mode API

## Status

Approved

## Execution authority

- Classification: Explicit approval granted
- Authority evidence: Acquisition-style due-diligence audit (2026-08-20, commit `42e71c2`),
  Blocker finding "The new API layer has no authentication at all"; explicit 2026-08-21
  user directive selecting the minimal shared-secret-gate remediation option over deferral
  or full session/JWT auth, given the imminent DevCon live-demo timeline.
- Implementation-ready: Yes
- Required escalation or approval, if any: None remaining — auth mechanism and scope were
  the one open decision and are resolved by this directive.

## Related findings or ADRs

- Finding/disposition: Due-diligence audit Blocker — `backend/app/api/v1/demo.py:273-387`
  (session start/end/moment/transcription routes, no `Depends()`), `kernel_status.py:366-368`
  (full status read, unauthenticated), `backend/app/main.py` (no `CORSMiddleware` anywhere).
- ADR: None required — this is an additive request-boundary control, not a new persistence,
  identity, or domain-authority model. If a future plan introduces per-operator identity or
  session-based auth, that work requires its own ADR.
- Engineering Directive: ED-0055.

## Problem statement

Every mutating and read endpoint under `/api/v1/*` (session lifecycle, moments,
transcription, kernel status, media timing evidence) is reachable by any client that can
route to the port, with no credential check and no CORS policy. This is safe only by
accident of network placement. It must close before this surface is ever reachable outside
a fully isolated, operator-controlled network, and should close now rather than be carried
as a known gap through a live multi-machine event.

## Verified current behavior

- `backend/app/api/v1/demo.py` — every `@router.post`/`@router.get` handler takes no
  dependency that checks a credential.
- `backend/app/api/v1/kernel_status.py` — status/workspace reads are unauthenticated.
- `backend/app/main.py` — FastAPI app construction registers no `CORSMiddleware`.
- The existing Demo launch-context mechanism (`docs/architecture` launch-scoped authority
  protection, PR #66) proves a request came from the current Demo launcher process; it does
  not gate access to any client that simply has network reach to the port.

## Desired behavior

A single shared-secret header check gates every route under the versioned API router(s)
used by the Demo/Event-Mode surface. A request without the correct secret is rejected
before any handler logic runs. An explicit, narrow CORS policy replaces the current
no-policy default. The existing launch-context mechanism is unchanged and remains a
second, independent layer above this gate.

## In scope

- One dependency (e.g. `require_api_secret`) applied at the router-include level (not
  copy-pasted per handler) to every route currently reachable under `/api/v1/*` used by
  Demo/Event-Mode, kernel status, and media timing evidence.
- Secret sourced from existing configuration/secret-resolution conventions (see
  `backend/app/core/config`) — fails closed if unset, consistent with the audit's own
  observed "secret resolution fails closed" strength. No new secret-storage mechanism.
- A header name and comparison using a constant-time equality check (`hmac.compare_digest`
  or equivalent) to avoid a timing side-channel.
- An explicit `CORSMiddleware` registration scoped to the actual Demo LAN origins the
  frontend is served from (no wildcard `*` origin combined with credentials).
- Updating the frontend Demo proxy (`frontend/app/api/stageflow/demo/[...path]/route.ts`)
  to attach the shared secret server-side when forwarding to the backend, so the browser
  never holds or transmits the raw secret.
- Tests proving: correct secret passes, missing/incorrect secret is rejected (401/403,
  not a raw 500), and the rejection happens before any handler-level side effect.

## Out of scope

- Per-operator identity, login, session tokens, or role-based access control.
- Any change to the existing launch-context mechanism's semantics.
- Public internet exposure, TLS termination, or a reverse proxy/gateway.
- Rotating or displaying the secret value in any log, report, or committed file.

## Constraints

- Architecture and terminology constraints: this is a transport/request-boundary control,
  not a Session/Program/Package authority change; it must not alter any human-authority
  decision path.
- Compatibility constraints: the existing Demo launcher and Producer UI must keep working
  without a manual step beyond configuring the shared secret once per deployment.
- Security and data-handling constraints: never print, log, or commit the secret value;
  presence-check only in any diagnostic output.

## Implementation approach

1. Add a configuration field for the shared secret, following the existing secret
   resolution pattern (fail closed if unset when the server starts with the Demo/API
   router enabled).
2. Add a FastAPI dependency performing a constant-time comparison against the configured
   secret, applied via `APIRouter(dependencies=[...])` or equivalent at include time so no
   individual handler can be added later without the check.
3. Register `CORSMiddleware` with an explicit allow-list of the Demo LAN frontend origin(s).
4. Update the frontend proxy route to attach the header from server-side configuration.
5. Add backend tests for authorized/unauthorized/missing-secret cases across at least one
   mutating and one read route; add a frontend proxy test confirming the header is attached
   and never exposed to the browser.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/core/config/*` | Add shared-secret configuration field, fail-closed if unset |
| `backend/app/api/v1/demo.py` | Apply auth dependency at router level |
| `backend/app/api/v1/kernel_status.py` | Apply auth dependency at router level |
| `backend/app/main.py` | Register `CORSMiddleware` with explicit origin allow-list |
| `frontend/app/api/stageflow/demo/[...path]/route.ts` | Attach shared secret server-side when forwarding |
| `backend/tests/test_demo_api.py` (or new test file) | Authorized/unauthorized/missing-secret coverage |
| `frontend/src/experience/demo-proxy.test.ts` | Confirm secret attached and not exposed to browser |

## Data or migration considerations

None. No schema, migration, or persisted-data change.

## Failure and recovery considerations

- Missing configured secret at startup must fail closed (server refuses to serve the
  gated routes, or refuses to start, consistent with existing "fails closed" convention) —
  it must never silently run unauthenticated.
- A rejected request must return a bounded, typed error (no stack trace, no internal detail)
  before touching the Kernel or repository.

## Observability requirements

- A rejected request should be distinguishable in existing logs/metrics from a legitimate
  4xx (e.g. `unauthorized` reason code), without logging the attempted or actual secret value.

## Test strategy

- Backend: correct secret → 200; missing header → 401/403; incorrect value → 401/403; no
  Kernel/repository side effect occurs on rejection.
- Frontend: proxy test confirms the outgoing request to the backend carries the header and
  that no code path returns or logs the secret to the browser/client.
- Full quality commands: `uv run pytest`, `uv run ruff check .`, `uv run pyright`,
  `npm.cmd test`, `npm.cmd run typecheck`, `npm.cmd run lint`, `npm.cmd run build`,
  `git diff --check`.

## Acceptance criteria

- [ ] Every route under the Demo/Event-Mode, kernel status, and media timing evidence
  routers rejects a request with a missing or incorrect shared secret before any handler
  logic runs.
- [ ] The check is applied at router-include level, not per-handler, so a newly added route
  is covered by default.
- [ ] An explicit CORS policy replaces the current no-policy default; no wildcard origin
  with credentials.
- [ ] The frontend proxy attaches the secret server-side; the browser never receives or
  transmits the raw secret value.
- [ ] A missing configured secret fails closed at startup, never silently unauthenticated.
- [ ] No secret value appears in logs, test output, committed files, or reports.
- [ ] Existing Demo launcher/Producer flow continues to work end-to-end with the secret
  configured.

## Rollback or reversal

Revert the dependency registration, CORS middleware, config field, and proxy header
change. No data or schema reversal required. Existing launch-context protection is
unaffected either way.

## Open questions

- None blocking. A future plan may replace this with per-operator identity/session auth;
  this plan does not preclude that and should be superseded rather than extended in place
  if that work begins.

## Completion record

_(To be filled in by whoever implements this plan.)_
