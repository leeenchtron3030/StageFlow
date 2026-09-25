# White-label presentation pass

## Status

Approved — sequenced after ED-0079

## Execution authority

- Classification: Green autonomous
- Authority evidence: [ADR-0031](../adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
  (Accepted 2026-09-24), decisions 1 and 5: no event, organizer, provider, or venue
  identity in operator-facing strings or default examples and fixtures; external
  publication frozen and removed from operator-facing workflow and documentation.
- Implementation-ready: Yes, once ED-0079 has landed. This plan relies on ED-0079's
  provider identifier on program-source results and its `[local_schedule]` configuration
  section. Use their names **as implemented** by ED-0079, not as guessed here.
- Required escalation or approval, if any: none. Stop and escalate if the work appears to
  require a public API or storage compatibility break, removing backend Devcon adapter
  code, changing Session or package authority, or rewriting historical documents.

## Related findings or ADRs

- ADR: ADR-0031, ADR-0028.
- Engineering Directive: ED-0080. Depends on ED-0079.

## Problem statement

Operators see Devcon throughout StageFlow even though it is no longer a target: "Program
refreshed · Devcon · just now", "Devcon session · …", "Provider: Devcon", "It never
publishes to Devcon", status entries named "Devcon program read" and "Devcon publication",
and launcher output announcing "StageFlow Demo 1 is ready". The example deployment
configuration hardcodes `test-devcon-8`, `razer-demo`, and "StageFlow Demo 1", and
frontend fixtures are built on Devcon identities. Publication is also still an advertised
operator action.

## Verified current behavior

- `frontend/src/components/demo-program-refresh-control.tsx` and
  `demo-start-session-control.tsx` hardcode "Devcon" in user-visible copy.
- `frontend/src/experience/kernel-adapter.ts` emits status items with ids `devcon-read`
  and `devcon-write` and labels "Devcon program read" and "Devcon publication".
- `scripts/demo/Start-StageFlowDemo.ps1` prints "StageFlow Demo 1 is ready at …", and
  `scripts/demo/StageFlow-Demo.ps1` matches that string when detecting readiness.
- `scripts/demo/StageFlow-Demo.ps1` exposes a `publish-devcon` action, documented in
  `scripts/demo/README.md`.
- `examples/demo-single-stage.toml.example` hardcodes `deployment_id = "razer-demo"`,
  `event_id = "test-devcon-8"`, and `name = "StageFlow Demo 1"`.
- Frontend tests such as `program-reconciliation.test.ts` use `test-devcon-8` and
  `devcon:`-prefixed keys as fixture data.

## Desired behavior

Every operator-facing surface is event- and provider-neutral. Program data is labelled by
the provider identifier carried in the data itself. Publication no longer appears as an
operator action. Default examples and fixtures use placeholder identities.

## In scope

- **Frontend copy:** replace hardcoded "Devcon" with the provider identifier from program
  data, rendered through a small display-name mapping (for example `local_file` → "Local
  schedule"). Neutral copy for status items, with ids renamed to neutral values
  (`program-read`, `publication`).
- **Publication freeze in the UI:** the publication status item reports "Frozen —
  awaiting Delivery design" and exposes no action.
- **Launcher output:** readiness messages become "StageFlow is ready at …"; update
  `StageFlow-Demo.ps1`'s readiness detection to match, keeping detection robust.
- **Publication freeze in tooling:** remove `publish-devcon` from the controller's
  documented action set and help. Invoking it refuses with a clear message citing
  ADR-0031 and performs no network call. Backend adapter code stays, dormant.
- **Examples:** make `examples/demo-single-stage.toml.example` use placeholder identities
  and ED-0079's `[local_schedule]` section by default, with Devcon shown only as a
  commented optional alternative.
- **Fixtures:** replace Devcon identities in frontend and backend test fixtures with
  neutral placeholders, except in tests that specifically exercise the Devcon adapter.
- **Current-state documentation:** README, `scripts/demo/README.md`, and current
  architecture documents describe Devcon as one optional adapter and publication as
  frozen.

## Out of scope

- Historical records: completed plans, reviews, validation results, and ADRs are not
  rewritten. They remain accurate history.
- Backend Devcon adapter code, ADR-0028, and migration `0009`.
- Any public API field or storage change. Kernel status field names are already neutral.
- Renaming source files or routes that contain "demo" — "Demo" describes a mode, not an
  event. A broader rename is not required by ADR-0031.
- Designing a Delivery context or any replacement publication path.

## Constraints

- No hardcoded provider or event names in operator-facing strings after this pass; the
  only permitted appearances are the provider display-name mapping and Devcon-adapter
  tests.
- Frontend changes stay presentation-only; the backend remains authority.
- Launcher readiness detection must not regress; the matched string and the emitted
  string change together.

## Implementation approach

1. Add the provider display-name mapping and replace hardcoded Devcon copy.
2. Rename the status item ids and labels; show publication as frozen.
3. Update launcher output and readiness detection together.
4. Freeze `publish-devcon` in the controller and runbook.
5. Neutralize the example configuration using ED-0079's section names.
6. Neutralize fixtures outside Devcon-adapter tests.
7. Update current-state documentation.
8. Add a white-label guard test that fails if hardcoded provider or event names reappear in
   operator-facing frontend components, excluding the display-name mapping.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `frontend/src/components/demo-program-refresh-control.tsx`, `demo-start-session-control.tsx` | Provider-neutral copy |
| `frontend/src/experience/kernel-adapter.ts` | Neutral status ids and labels; publication frozen |
| `frontend/src/experience/*.test.ts` | Neutral fixtures; white-label guard test |
| `scripts/demo/Start-StageFlowDemo.ps1`, `StageFlow-Demo.ps1`, `scripts/demo/README.md` | Neutral readiness; publication frozen |
| `examples/demo-single-stage.toml.example` | Placeholder identities; local schedule default |
| `README.md`, current architecture docs | Devcon as optional adapter; publication frozen |

## Data or migration considerations

None.

## Failure and recovery considerations

A refused `publish-devcon` invocation exits non-zero with a clear message and performs no
network call or state change.

## Observability requirements

Not applicable beyond the neutral status labels.

## Test strategy

- Frontend: `npm run test`, `npm run lint`, `npm run typecheck`, `npm run build`,
  including the new white-label guard test.
- PowerShell AST parsing for changed scripts; a focused test that the frozen action
  refuses without network access.
- Backend suite for any fixture changes; Ruff and Pyright.

## Acceptance criteria

- [ ] No hardcoded provider or event name remains in operator-facing frontend strings,
  outside the provider display-name mapping.
- [ ] Program data is labelled by its provider identifier.
- [ ] Status items use neutral ids and labels; publication shows as frozen with no action.
- [ ] Launcher output and readiness detection are neutral and still work.
- [ ] `publish-devcon` is removed from the documented action set and refuses with a clear
  ADR-0031 message, making no network call.
- [ ] The example configuration uses placeholder identities and the local schedule
  source by default.
- [ ] Fixtures outside Devcon-adapter tests use neutral placeholders.
- [ ] A white-label guard test prevents regression.
- [ ] Historical documents, backend adapter code, API fields, and storage are unchanged.
- [ ] Frontend and backend checks pass, apart from known environmental failures.

## Rollback or reversal

Presentation, tooling, examples, and fixtures only; directly revertible.

## Open questions

- None blocking.

## Completion record

_(To be filled in by whoever implements this plan.)_
