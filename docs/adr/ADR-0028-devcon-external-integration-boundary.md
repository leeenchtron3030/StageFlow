# ADR-0028: Bounded Devcon external integration boundary

## Status

Accepted

## Date

2026-08-21

## Context

StageFlow already ships a bounded Devcon integration used by the Demo 1 and prospective
Devcon event workflow. The implementation arrived through completed Demo plans before
the Engineering Directive convention resumed, so its durable boundary and failure
semantics were distributed across code, tests, runbooks, and completion evidence rather
than one ADR. ED-0065 records the already-accepted decision retroactively; it does not
authorize a broader integration or a new external write.

Devcon remains authoritative for its public program and the upstream Session enrichment
document. StageFlow remains authoritative for its own Business Event, Stage, Program
Expectation revisions, realized Session, media association, package revision, transcript
evidence, and human approval. The integration must preserve planned versus observed
reality, human publication authority, offline-capable event operation, bounded external
I/O, and sanitized failure reporting.

The shipped integration has two intentionally different paths:

- an optional public read adapter fetches one configured Devcon Event/room program and
  reconciles a complete successful snapshot into durable external Program Expectations;
- a guarded Demo controller can publish exactly `transcript_text` and `duration` for one
  selected upstream Session only after the corresponding StageFlow package revision is
  complete, approved, reviewable, and explicitly confirmed by digest.

The first guarded live publication exposed two external-system lessons. The upstream
write contract is the source-update route with an `x-api-key`, not the general Session
route. Separately, HTTP write acceptance, Git-backed upstream durability, and public API
cache convergence are distinct facts: an immediate cached public GET cannot overturn a
durably accepted write.

## Decision

### Boundary and ownership

Devcon-specific HTTP behavior remains in `app.infrastructure.devcon`. Program-source
contracts and reconciliation live behind the bounded integration context; Devcon
payloads do not become Kernel aggregates or provider-specific core models. The shipped
integration is a named Devcon adapter, not a claim that StageFlow has a generalized
publication platform.

Program items become revisioned External Program Expectations. They may supply planned
title, speaker, room, and schedule context, but they do not create a realized Session,
select its actual Stage, set authoritative boundaries, associate media, approve a
package, or establish what occurred. A successful complete snapshot may add, change,
withdraw, or restore expectations while preserving stable StageFlow identity and
history. Fetch, pagination, contract, or storage failure preserves the last successful
snapshot.

### Read behavior

The read adapter is optional configuration. It uses bounded HTTPS GET requests to the
official configured Devcon API, validates the response envelope and every consumed
field, enforces pagination and catalog byte/count bounds, filters to one exact
Event/room scope, requires aware schedule timestamps, and rejects identity conflicts or
a catalog that changes mid-read. Startup synchronization and explicit Producer refresh
are the only current refresh triggers; there is no uncontrolled poller in the accepted
mainline baseline.

Devcon unavailability degrades only external planned-context freshness. It must not stop
local media discovery, Session/media authority, package review, transcription already
eligible locally, or reconstruction from PostgreSQL. The last successful Program
Expectation snapshot remains visible while the provider is unavailable.

### Guarded write behavior

The current write is a Demo-specific, explicitly human-confirmed enrichment operation,
not automatic publication. Before any PUT, StageFlow requires one exact realized
Session, authoritative presentation end, an approved exact package revision, complete
non-truncated transcript evidence for that package membership, matching Devcon Event and
Session external identities, and a preview digest that still matches at execution time.

The adapter writes only to the official Devcon source-update endpoint and sends exactly
two UTF-8 JSON fields: `transcript_text` and integer `duration`. The credential is
required at the execution boundary, sent only as `x-api-key`, and is never placed in a
URL, repository document, result, log, or durable StageFlow record. Arbitrary upstream
error bodies are bounded and reduced to allowlisted reason codes.

There is no automatic PUT retry, compensation, background publication, additional field
write, or generic API route that grants publication authority. A rejected or ambiguous
write requires another explicit human decision; read-back state never triggers a write.
Any broader publication workflow, automated retry, credential model, provider, or field
set requires a separate accepted decision and implementation plan.

### Verification and failure semantics

The controller records three separate outcomes:

1. **Write acceptance:** the official endpoint accepted the one PUT.
2. **Durable upstream state:** a cache-bypassing read of the exact Git-backed upstream
   event/session document matches the expected transcript and duration.
3. **Public API convergence:** bounded GET-only polling observes the public cached API
   converge, remain stale, or become unavailable.

A write rejection performs no durability or convergence reads. Durable mismatch and
remote identity mismatch fail closed. Public API staleness after durable verification is
reported as stale convergence, not as a failed write and never as grounds to retry.
Bounded verification failure does not mutate StageFlow Session, package, transcript, or
approval authority.

### Offline and product constraints

Devcon network access is optional enhancement. Core event production remains locally
capable, and the Producer must be able to distinguish unavailable provider context from
unavailable StageFlow authority. Devcon terminology and endpoints remain adapter details;
StageFlow is still event-agnostic and must not require code changes for the next
conference integration.

This ADR records an already-shipped controlled Demo boundary. It does not classify the
integration as production deployment or event readiness, authorize customer-data use in
tests, or resolve publication-era late-media, retention, deletion, or generalized
delivery semantics.

## Alternatives

### Treat the integration as disposable Demo scaffolding

Rejected. It is exercised as a real prospective-customer boundary and has durable
Program Expectation, package-approval, request-contract, and verification behavior that
must remain governed even if later generalized.

### Build a generic publication framework before documenting Devcon

Rejected. There is one concrete provider and one bounded enrichment operation. A generic
framework would select payload, retry, delivery, reconciliation, and authority semantics
without another demonstrated consumer.

### Import Devcon Sessions directly as StageFlow Sessions

Rejected. It collapses planned and observed reality, gives an external system Session
realization authority, and conflicts with ADR-0023 and ADR-0024.

### Retry publication automatically until public GET matches

Rejected. The external operation can have succeeded while the public cache remains stale;
retrying would duplicate an irreversible external side effect and bypass explicit human
authority.

### Treat immediate public API state as durability authority

Rejected by observed behavior. The public endpoint may serve stale-while-revalidate
content after the Git-backed source is durably updated.

## Consequences

### Positive

- Devcon ownership and StageFlow authority remain explicit and independently testable.
- Network/provider failure degrades planned context or publication verification without
  stopping the local event-critical path.
- The one external write stays narrow, human-confirmed, replay-resistant, and
  privacy-conscious.
- Write acceptance, durable state, and cache convergence are reported honestly.
- Later providers can introduce their own adapters without importing Devcon contracts
  into the Kernel.

### Negative and risks

- The current write path is Demo/controller-specific rather than a durable generalized
  delivery operation.
- Upstream route, schema, repository layout, and cache policy can change independently;
  contract tests and live read-only checks must detect drift.
- Publication cannot complete offline and has no automatic retry or compensation.
- The GitHub durability check adds a second external read dependency for strong
  verification.
- Single configured Event/room reconciliation does not establish multi-stage room-move
  semantics.

## Validation

The accepted implementation is covered by:

- bounded program pagination, contract, complete-snapshot, failure-preservation,
  withdrawal/restoration, and Session-authority-isolation tests;
- exact request URL/method/header/body, Unicode, response-bound, rejection, no-retry,
  identity, durable-read, and public-cache convergence tests;
- package approval/revision, complete transcript projection, preview digest, and explicit
  confirmation tests;
- completion evidence showing the corrected request contract and separation of durable
  success from public API staleness; and
- privacy checks that retain no credential, transcript content, provider body, or source
  path in logs or validation artifacts.

No new external write is required to validate this ADR. Future contract changes should
prefer fake-request/local-server tests and read-only live verification; each real PUT
remains an explicitly approved external action.

## Related documents

- [Product Constitution](../../PRODUCT_CONSTITUTION.md)
- [ADR-0023: Session authority and completion](ADR-0023-session-authority-and-completion.md)
- [ADR-0024: Durable Kernel authority and persistence](ADR-0024-durable-kernel-authority-and-persistence.md)
- [Demo single-stage vertical slice plan](../plans/demo-single-stage-vertical-slice.md)
- [Program Expectation snapshot reconciliation](../plans/program-expectation-reconciliation.md)
- [Demo Package Approval](../plans/demo-package-approval.md)
- [Demo Devcon publication contract correction](../plans/demo-devcon-publication-contract.md)
- [Demo Devcon post-publish verification correction](../plans/demo-devcon-post-publish-verification.md)
- [Demo hardware rehearsal](../plans/demo-hardware-rehearsal.md)
