# ADR-0031: White-label product identity and provider-neutral program sources

## Status

Accepted

## Date

2026-09-24

## Context

StageFlow was always intended to be a white-label product: a live-event media system any
organizer can deploy for their own events. During the Demo 1 and Demo 2 cycles, however,
development targeted one specific deployment — the Devcon event — and the project used a
Devcon test API (event `test-devcon-8`) as its only real schedule source and its only
external write target.

On 2026-09-24 the repository owner confirmed that StageFlow is no longer being built to run
at that event, and directed that the product be white-labeled in all aspects, with testing
and Devcon-specific practices refocused on core StageFlow functions.

The Devcon integration code is correctly isolated in adapter packages
(`backend/app/infrastructure/devcon/`, `backend/app/contexts/integration/devcon/`), as
ADR-0005 and [ADR-0028](ADR-0028-devcon-external-integration-boundary.md) intended.
Direct inspection on 2026-09-24 found that Devcon has nonetheless leaked outside those
adapters:

- **Kernel domain:** `program_reconciliation.py` reads
  `external_references["devcon_session_id"]`, a provider-specific key inside core
  Program Expectation reconciliation.
- **Deployment configuration:** `devcon_read` is a first-class configuration section, its
  base URL is hard-locked to `https://api.devcon.org`, and the `demo-single-stage` runtime
  profile rejects any configuration without it. A deployment cannot run without Devcon.
- **Operator UI:** user-visible labels such as "Program refreshed · Devcon" and "Devcon
  session", and status entries named "Devcon program read"/"Devcon write".
- **Tooling, examples, and fixtures:** launcher output ("StageFlow Demo 1 is ready"), an
  example configuration hardcoding `test-devcon-8` and `razer-demo`, and test fixtures
  built on Devcon keys.

Migration `0009` also contains Devcon-specific backfill SQL. It is an already-applied
historical migration and is out of scope for change.

## Decision

1. **StageFlow is white-label.** No event, organizer, provider, or venue identity may
   appear in core domain logic, schema defaults, configuration defaults, operator-facing
   strings, or default examples and fixtures. Event identity comes from deployment
   configuration. Provider names may appear only inside provider adapters and in
   provider-attributed data returned from them.

2. **Program schedule sources sit behind a provider-neutral port.** The port's shape is
   taken from the existing, working `DevconProgramSync` surface: synchronize a Stage's
   program, probe availability, and read the durable cached program. Devcon becomes one
   optional adapter implementing it.

3. **A local schedule-file adapter is the default source** for development, tests,
   fixtures, and rehearsals. It is offline-first and needs no external API, consistent
   with the Constitution's local-first principle.

4. **Core domain logic uses provider-neutral external reference keys.** Provider-specific
   keys remain readable only through an explicit compatibility fallback for data already
   persisted, with documented removal criteria.

5. **External publication is frozen.** The Devcon publish adapter is retained but dormant.
   It is removed from operator-facing workflow and documentation, and no new publication
   work proceeds until a provider-neutral Delivery context is designed. This decision
   grants no new external write capability and removes none that a future Delivery ADR
   may reintroduce through a provider-neutral boundary.

6. **Validation and rehearsal procedures must not require any external provider API.**

7. **ADR-0028 is narrowed, not superseded.** Its description of the Devcon adapter
   boundary, failure modes, and verification semantics remains accurate for the adapter.
   This ADR changes Devcon's role from target integration to optional adapter, and freezes
   its write path.

## Alternatives

### Remove the Devcon integration entirely

Rejected. The adapter is working, tested, and correctly isolated, and it is a useful
reference implementation for future provider adapters. Removal would discard that without
improving white-label correctness, which depends on what leaks *outside* adapters, not on
whether one exists.

### Keep Devcon as the default schedule source

Rejected. A white-label product cannot default to one organizer's API, and a default that
requires Internet access contradicts local-first Event operation.

### Manual Program Expectation entry as the only neutral source

Rejected as the default. It avoids designing a file format but makes repeatable test
events slow to set up, which undermines the goal of refocusing testing on core functions.
Manual entry remains a reasonable future capability.

### Generalize publication now

Rejected for now. With no second delivery target, a provider-neutral publication port
would be designed against a single example. Freezing publication until a Delivery context
exists avoids a premature abstraction and removes Devcon from operator workflow
immediately.

## Consequences

### Positive

- Any organizer can deploy StageFlow without Devcon configuration, credentials, or
  Internet access.
- Testing, fixtures, and rehearsals become repeatable and offline.
- The provider-neutral port gives future schedule providers a defined seam.
- Operator-facing surfaces stop naming an event StageFlow no longer targets.

### Negative

- A compatibility fallback for provider-specific external reference keys must be carried
  until persisted data no longer depends on it.
- Configuration gains a second schedule-source form; existing external Demo configuration
  using `[devcon_read]` must remain accepted during transition.
- Demo 2 (PR #71) polls Devcon from its autonomous coordinator and must be generalized to
  the port before its remaining rehearsal criteria can be exercised against a neutral
  source.
- Publication capability is paused rather than generalized, so no external delivery
  target exists until a Delivery context is designed.

## Validation

None yet. Implementation proceeds through ED-0079 (provider-neutral program source and
configuration decoupling), ED-0080 (white-label presentation pass and publication freeze),
and a later directive generalizing Demo 2. A white-label acceptance check — no provider or
event identity in core domain, configuration defaults, or operator-facing strings — is
part of those directives' acceptance criteria.

## Related documents

- [ADR-0028](ADR-0028-devcon-external-integration-boundary.md) — Devcon adapter boundary,
  narrowed by this ADR.
- ADR-0004 and ADR-0005 (in `ARCHITECTURE_DECISIONS.md`) — StageFlow owns workflow, not
  conference data; external integrations use adapters.
- `PRODUCT_CONSTITUTION.md` — local-first and Offline-First Event Operations principles.
- [Demo 2 hardware rehearsal Run 001](../validation/results/demo2-hardware-rehearsal-001.md)
  — criteria 4, 6, and 7 remain to be exercised, now against a neutral source.
