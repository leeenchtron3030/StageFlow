# Provider-neutral program source

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: [ADR-0031](../adr/ADR-0031-white-label-identity-and-provider-neutral-program-sources.md)
  (Accepted 2026-09-24), decisions 2, 3, 4, and 6: program schedule sources sit behind a
  provider-neutral port shaped from the existing `DevconProgramSync`; a local
  schedule-file adapter is the default; core logic uses provider-neutral reference keys
  with a compatibility fallback; validation must not require an external API. ADR-0005
  (external integrations use adapters); ADR-0028 (Devcon adapter boundary, narrowed by
  ADR-0031).
- Implementation-ready: Yes. ADR-0031 resolved the direction; the choices below are
  bounded implementation details.
- Required escalation or approval, if any: none. Stop and escalate if the work appears to
  require changing Program Expectation authority semantics, editing an applied migration,
  removing Devcon support, changing publication behavior, or modifying the Demo 2 branch.

## Related findings or ADRs

- ADR: ADR-0031, ADR-0028, ADR-0005, ADR-0004.
- Engineering Directive: ED-0079. ED-0080 (white-label presentation pass) and the later
  Demo 2 generalization depend on it.

## Problem statement

StageFlow cannot run without Devcon. The only program schedule source is
`DevconProgramSync`; `DeploymentConfiguration` hard-locks its base URL to
`api.devcon.org`; the `demo-single-stage` runtime profile rejects configuration without a
`[devcon_read]` section; and core Program Expectation reconciliation reads the
provider-specific key `devcon_session_id`. A white-label deployment — or a repeatable
offline test event — has no way in.

## Verified current behavior

- `backend/app/contexts/integration/devcon/service.py` defines `DevconProgramSync` with
  `synchronize(*, event_id, stage_id) -> ProgramSyncResult`, `probe() -> int`, and
  `cached_program(*, event_id) -> tuple[ProgramExpectation, ...]`.
- `backend/app/bootstrap/event_mode_kernel.py` composes `KernelComponents.devcon_program_sync`
  and exposes `sync_devcon_program()`.
- Consumers on `main`: `backend/app/api/v1/demo.py` (program refresh route) and
  `backend/app/demo/cli.py` (`preflight`, `sync-program`). On the unmerged Demo 2 branch,
  `backend/app/demo/autonomous.py` also calls these names.
- `backend/app/core/config/deployment.py` defines `DevconReadConfiguration` (base URL
  locked to `https://api.devcon.org`, `event_id`, `room_id`, paging and timeout) and the
  `demo-single-stage` profile validator requires `devcon_read`.
- `backend/app/contexts/production/event_mode_kernel/program_reconciliation.py` sets
  `external_session_id=expectation.external_references.get("devcon_session_id")`.
- `backend/app/api/v1/kernel_status.py` reads `devcon_event_id`, `devcon_session_id`, and
  `devcon_room_id` to populate neutrally named response fields.
- `backend/app/api/v1/demo.py` imports and catches `DevconReadError` from Devcon
  infrastructure.
- Migration `0009` backfills Devcon-shaped synchronization scopes. It is applied history.

## Desired behavior

A deployment can supply its program from a local schedule file, with no Devcon
configuration, credentials, or Internet access, through the same port Devcon now
implements. Core reconciliation is provider-neutral. Existing Devcon configurations and
persisted data keep working.

## Design decisions

1. **Port:** a `ProgramScheduleSource` protocol with the three methods `DevconProgramSync`
   already exposes. `DevconProgramSync` conforms without behavior change. The protocol
   lives in `backend/app/contexts/integration/` beside, not inside, the Devcon package.
2. **Local schedule file:** one versioned JSON format, validated strictly. It carries a
   schema version, the configured Event key, and a list of sessions each with a stable
   external session key, title, speaker display strings, Stage key, and timezone-aware
   planned start and end. Unknown fields, naive timestamps, duplicate keys, and unknown
   Stage keys are rejected with typed errors. No CSV in this slice.
3. **Configuration:** add a `[local_schedule]` section (a file path and nothing
   provider-specific). The `demo-single-stage` profile requires **exactly one** of
   `[local_schedule]` or `[devcon_read]`. `[devcon_read]` keeps its current meaning, so
   existing external configurations remain valid.
4. **Composition names:** `KernelComponents` gains `program_source` and `sync_program()`.
   `devcon_program_sync` and `sync_devcon_program()` remain as **documented compatibility
   aliases**, removable once the Demo 2 branch no longer calls them.
5. **Neutral reference keys:** core code reads `external_session_id`, `external_event_id`,
   and `external_room_id` from `external_references`, falling back to the legacy
   `devcon_session_id`, `devcon_event_id`, and `devcon_room_id` keys for data already
   persisted. This applies to both `program_reconciliation.py` and
   `backend/app/api/v1/kernel_status.py`, whose API response fields are already neutral and
   do not change. The Devcon adapter writes the neutral keys for new data. The fallback's
   removal criterion is documented.
6. **Neutral error type:** a provider-neutral `ProgramSourceUnavailableError`, which the
   Devcon adapter's `DevconReadError` maps to or subclasses, so `demo.py` and the CLI stop
   importing Devcon infrastructure errors.
7. **Provider attribution:** each source reports a provider identifier (`local_file`,
   `devcon`) carried in its results, so later presentation can label program data from
   data rather than hardcoded strings.

## In scope

- The `ProgramScheduleSource` port and Devcon conformance.
- A local schedule-file adapter and its strict JSON parser.
- `[local_schedule]` configuration and the exactly-one-source profile rule.
- Neutral composition names with compatibility aliases; API and CLI switched to them.
- The neutral reference keys with legacy fallback, in reconciliation and Kernel status.
- The provider-neutral source error type.
- A provider identifier on source results.
- A small neutral example schedule file under `examples/`, using placeholder identities.
- Behavior-first tests, with no network access required.
- Configuration README, architecture, and glossary updates directly affected.

## Out of scope

- Operator-facing string changes, launcher output, example deployment configuration, and
  frontend fixtures — ED-0080.
- Publication, the `publish-devcon` path, or any external write.
- Modifying the Demo 2 branch or `autonomous.py` — a later directive.
- Editing migration `0009` or any applied migration; new migrations are not needed.
- CSV import, manual entry, or any additional provider.
- Removing Devcon support.

## Constraints

- White-label: no provider name in the port, the local adapter, core reconciliation, or
  configuration defaults. Provider names remain only inside the Devcon adapter and in
  provider-attributed data.
- Offline: the local adapter performs no network access.
- Compatibility: existing `[devcon_read]` configurations, persisted `devcon_session_id`
  references, API routes, and CLI commands keep working unchanged.
- Program Expectations remain External context and never realize a Session.

## Implementation approach

1. Define `ProgramScheduleSource`; verify `DevconProgramSync` conforms.
2. Implement the local schedule-file parser and adapter, reusing Program Expectation
   contracts and the durable cache path Devcon already uses.
3. Add `[local_schedule]` and the exactly-one-source profile rule.
4. Add `program_source`/`sync_program()` and the compatibility aliases; switch
   `demo.py` and `cli.py` to the neutral names.
5. Introduce the neutral reference key with legacy fallback.
6. Add the example schedule file and documentation.
7. Add behavior-first tests.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `backend/app/contexts/integration/program_source.py` | Provider-neutral port (new) |
| `backend/app/contexts/integration/local_schedule/` | Local schedule-file adapter (new) |
| `backend/app/contexts/integration/devcon/service.py` | Port conformance; neutral key; provider id |
| `backend/app/core/config/deployment.py`, `core/config/README.md` | `[local_schedule]`; exactly-one-source rule |
| `backend/app/bootstrap/event_mode_kernel.py` | Neutral composition names plus aliases |
| `backend/app/contexts/production/event_mode_kernel/program_reconciliation.py` | Neutral key with fallback |
| `backend/app/api/v1/kernel_status.py` | Neutral keys with fallback; response fields unchanged |
| `backend/app/api/v1/demo.py`, `backend/app/demo/cli.py` | Use neutral names and error type |
| `examples/local-schedule.example.json` | Neutral example schedule (new) |
| `backend/tests/test_provider_neutral_program_source.py` | Behavior-first tests (new) |

## Data or migration considerations

No migration. Persisted `devcon_session_id` references remain readable through the
fallback. New Devcon-sourced data carries the neutral key.

## Failure and recovery considerations

- A malformed or unreadable schedule file fails synchronization with a typed, bounded
  error and leaves the existing cached program intact, matching Devcon's unavailability
  behavior.
- A configuration supplying both or neither source fails validation with a clear message.

## Observability requirements

Program synchronization results and status report the provider identifier without file
paths or credentials.

## Test strategy

- Behavior-first: valid file import; each rejection case; cached program after a failed
  re-read; exactly-one-source validation; legacy `[devcon_read]` still accepted; Devcon
  conformance to the port; neutral key read and legacy fallback; aliases resolving to the
  neutral implementation; provider identifier propagation.
- No test may require network access or Devcon credentials.
- Full backend suite, Ruff, Pyright.

## Acceptance criteria

- [ ] `ProgramScheduleSource` exists; `DevconProgramSync` conforms without behavior change.
- [ ] A local schedule-file adapter imports a strict, versioned JSON schedule offline.
- [ ] The `demo-single-stage` profile accepts exactly one of `[local_schedule]` or
  `[devcon_read]`; existing Devcon configurations remain valid.
- [ ] `program_source`/`sync_program()` exist; Devcon names remain as documented aliases.
- [ ] Reconciliation and Kernel status read neutral keys, with a documented legacy
  fallback; Kernel status response fields are unchanged.
- [ ] API and CLI code no longer import Devcon infrastructure errors.
- [ ] Source results carry a provider identifier.
- [ ] No provider name appears in the port, local adapter, core reconciliation, or
  configuration defaults.
- [ ] No test requires network access or Devcon credentials.
- [ ] Full backend suite, Ruff, and Pyright pass, apart from known environmental failures.
- [ ] No migration, publication, Demo 2 branch, or Program Expectation authority change.

## Rollback or reversal

Additive and reversible: remove the port, adapter, configuration section, neutral names,
and fallback. The Devcon path is unchanged throughout, so reverting restores prior
behavior.

## Open questions

- None blocking.

## Completion record

_(To be filled in by whoever implements this plan.)_
