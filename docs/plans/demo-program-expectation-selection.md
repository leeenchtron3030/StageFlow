# Demo Program Expectation selection

## Status

Completed

## Execution authority

- Classification: Green, explicitly authorized by the 2026-08-19 Demo Producer UX directive.
- Authority evidence: the accepted Demo single-stage UI/API boundary, the existing optional
  `program_expectation_id` Start Session contract, external Program Expectation semantics, and the
  explicit instruction to require a human expectation or ad-hoc selection.
- Implementation-ready: Yes.
- Escalation boundary: Kernel Session semantics, schedule-driven authority, Devcon contracts,
  schemas, migrations, or trust-boundary changes remain out of scope.

## Problem statement

Kernel status contains every Stage Program Expectation, but the Stage view projects only one
`nextExpectation`, and Start Session omits the already-supported internal durable expectation ID.
The Producer therefore cannot inspect and explicitly bind a Session start to one of the four
external Devcon-backed expectations.

## Desired behavior

The Demo Stage view displays all Stage expectations in deterministic planned-start order and
labels them external evidence. The human selects exactly one durable expectation or a separate
ad-hoc option before Start Session becomes available. Confirmation names the selection, and the
request sends only the selected internal Program Expectation ID as authority input.

## In scope

- Stage Program Expectation view-model projection and deterministic sorting.
- Bounded display of title, speakers, time, provider, and external Devcon session provenance.
- Explicit expectation/ad-hoc radio selection and fail-closed Start Session submission.
- Focused adapter, submission, UI-source, and existing launch-context regressions.
- Proportionate frontend/backend validation and zero-Session live read-back.

## Out of scope

- Backend production changes, automatic Session creation, schedule inference, Devcon writes,
  package approval, Arm Event semantics, schemas, migrations, dependencies, or worker reporting.

## Acceptance criteria

- [x] All current Stage expectations render as external evidence in planned-start order.
- [x] Exactly one durable expectation or explicit ad-hoc choice is required.
- [x] Expectation confirmation names the selected talk and sends its internal durable ID.
- [x] Ad-hoc confirmation is explicit and sends no expectation ID.
- [x] No selection, missing actor, missing context, or declined confirmation sends a POST.
- [x] Existing stale/missing launch-context proxy behavior remains green.
- [x] No implementation or validation action creates a Session in the live rehearsal Event.
- [x] Focused and normal validation passes with no schema, dependency, or backend change.

## Rollback

Revert the frontend view-model, selection helper/UI, tests, styles, and plan. Preserve the running
Demo Event and all durable state.

## Completion record

- Implemented revision: working tree on `codex/demo-program-expectation-selection`.
- Validation: `npm test` (34 passed), `npm run typecheck`, `npm run lint`, and
  `npm run build`; focused backend `uv run pytest -p no:cacheprovider tests/test_demo_api.py
  tests/test_demo_authority.py tests/test_durable_event_mode_kernel.py -q` passed 41 tests
  with one existing Starlette/httpx deprecation warning; `git diff --check` passed.
- Live rehearsal result: the same Event was relaunched after the production build; controller and
  direct `stageflow_demo` read-back both reported zero Sessions, four external expectations, and
  an empty recordings source. The live Stage page rendered four cards and a disabled Start button.
- Warnings and remaining work: no new Yellow decision; worker `not_current` reporting remains
  outside this milestone as previously bounded.
