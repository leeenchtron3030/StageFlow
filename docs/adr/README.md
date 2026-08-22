# Architecture Decision Records

## Purpose

An ADR records a durable architectural choice, its alternatives, and consequences. ADRs
govern future work after acceptance; they do not prove that the decision is implemented.
Implementation status belongs in the index, plans, Engineering Directives, and code.

ADR-0001 through ADR-0018 remain preserved in the historical monolithic
[Architecture Decisions](../../ARCHITECTURE_DECISIONS.md) file. New ADRs use individual
files in this directory. Do not duplicate the earlier ADR text merely to normalize the
layout.

## Naming and numbering

Use:

```text
ADR-NNNN-short-kebab-case-title.md
```

- Allocate the next unused four-digit number.
- Never renumber or reuse a published number.
- Keep the title stable; use supersession rather than rewriting a decision's identity.
- Reserved ADR numbers remain reserved.

## Statuses

- **Proposed:** complete enough for review but not authority.
- **Accepted:** approved and authoritative.
- **Rejected:** considered and explicitly not selected.
- **Deprecated:** still historical but no longer recommended for new work.
- **Superseded:** replaced by one or more linked ADRs.
- **Reserved:** number intentionally unavailable and contains no decision.

Implementation state—unimplemented, partial, or implemented—is tracked separately and
does not change ADR status.

## Required sections

Every new ADR contains:

1. Title
2. Status
3. Date
4. Context
5. Decision
6. Alternatives
7. Consequences
8. Validation
9. Related documents

## When an ADR is required

Use an ADR for a durable decision with meaningful alternatives or broad consequences,
especially Session authority, persistence/transaction ownership, identity/replay,
execution semantics, time authority, configuration precedence, cross-context ownership,
or an external side-effect boundary.

An ADR is not required for a local implementation detail already constrained by accepted
architecture, a small reversible correction, or an unapproved idea. Reviews identify
issues; dispositions decide whether an ADR candidate should proceed.

## Supersession

Do not edit an accepted ADR to reverse its decision. Create a new ADR that explains the
new context and names every superseded ADR. Update this index and mark the older record
`Superseded by ADR-NNNN`. Keep both records available.

## ADR index

| ADR | Decision | Status | Implementation note |
| --- | --- | --- | --- |
| [ADR-0001](../../ARCHITECTURE_DECISIONS.md) | Modular monolith | Accepted | Implemented/protected |
| [ADR-0002](../../ARCHITECTURE_DECISIONS.md) | Sessions are primary Production aggregate | Accepted | Authoritative Session aggregate implemented in the bounded Kernel; post-Kernel evolution remains open |
| [ADR-0003](../../ARCHITECTURE_DECISIONS.md) | Media chunks are storage artifacts | Accepted | Preserved by candidate/readiness/asset separation |
| [ADR-0004](../../ARCHITECTURE_DECISIONS.md) | StageFlow owns workflow, not conference data | Accepted | External systems not implemented |
| [ADR-0005](../../ARCHITECTURE_DECISIONS.md) | External integrations use adapters | Accepted | Contracts align; provider adapters absent |
| ADR-0006 | Reserved | Reserved | No decision |
| ADR-0007 | Reserved | Reserved | No decision |
| ADR-0008 | Reserved | Reserved | No decision |
| [ADR-0009](../../ARCHITECTURE_DECISIONS.md) | Verification preserves reasoning history | Accepted | Contracts implemented; no durable workflow |
| [ADR-0010](../../ARCHITECTURE_DECISIONS.md) | Timeline candidates are not Operational Products | Accepted | Current `SessionWindow` alias needs compatibility decision |
| [ADR-0011](../../ARCHITECTURE_DECISIONS.md) | Production Events are universal ingress | Accepted | Contracts partial; dispatcher/media bridges need stabilization |
| [ADR-0012](../../ARCHITECTURE_DECISIONS.md) | Recorded media anchors observable reality | Accepted | Aligned in reasoning contracts |
| [ADR-0013](../../ARCHITECTURE_DECISIONS.md) | Planned and observed reality remain separate | Accepted | Aligned in contracts |
| [ADR-0014](../../ARCHITECTURE_DECISIONS.md) | Runtime component status should become shared | Accepted | Future consolidation; not a current rewrite mandate |
| [ADR-0015](../../ARCHITECTURE_DECISIONS.md) | Interpreters produce objective Observations | Accepted | Concrete contracts implemented |
| [ADR-0016](../../ARCHITECTURE_DECISIONS.md) | ObservationLocation is location authority | Accepted | Implemented in Observation contracts |
| [ADR-0017](../../ARCHITECTURE_DECISIONS.md) | Observation traceability should become first-class | Accepted | Future contract correction |
| [ADR-0018](../../ARCHITECTURE_DECISIONS.md) | Observation payloads may need first-class modeling | Accepted | Future capability; not authorized yet |
| [ADR-0019](ADR-0019-stable-ingress-and-interpreter-boundary.md) | Stable ingress identity and one dispatcher-facing interpreter protocol | Accepted | Both boundaries implemented; ingress and Kernel persistence verified on isolated real PostgreSQL |
| [ADR-0020](ADR-0020-canonical-media-to-event-path.md) | Canonical candidate-to-asset-to-Event path | Accepted | Bounded durable filesystem candidate-to-asset-to-stable-ingress path implemented |
| [ADR-0021](ADR-0021-time-authority.md) | Domain and infrastructure time authority | Accepted | Strict-aware internal transition implemented |
| [ADR-0022](ADR-0022-postgresql-authoritative-operational-store.md) | PostgreSQL authoritative operational store | Accepted | Ingress and bounded Kernel authority are composed; broader durable workflows remain future work |
| [ADR-0023](ADR-0023-session-authority-and-completion.md) | Session meaning, Stage invariants, association, boundaries, and completion authority | Accepted | Kernel Session aggregate, package approval/revision, and typed history implemented |
| [ADR-0024](ADR-0024-durable-kernel-authority-and-persistence.md) | Explicit bootstrap, human Session realization, deterministic association, normalized state/history | Accepted | Kernel corrections and Green follow-up are closure-validated |
| [ADR-0025](ADR-0025-postgresql-durable-operations-and-workers.md) | PostgreSQL-backed Durable Operations, attempts, leases, and Worker coordination | Accepted | First transcription-worker substrate implemented under the bounded Green plan; real provider/model and automatic enqueue remain unselected |
| [ADR-0026](ADR-0026-policy-scoped-automatic-authority.md) | Evidence-to-policy-to-authority evaluation with scoped activation and durable provenance | Proposed | Yellow decision; no implementation |
| [ADR-0027](ADR-0027-media-timing-evidence.md) | Dedicated durable revisioned advisory Media Timing Evidence linked to Completed Media Asset | Accepted | MTE v1 implemented; recorder qualification and automatic authority remain Yellow |
| [ADR-0028](ADR-0028-devcon-external-integration-boundary.md) | Bounded Devcon program-read and guarded human-confirmed enrichment-write boundary | Accepted | Retroactively documents the shipped Demo integration and its failure/verification semantics; no new external write |

## Unresolved ADR candidates

| Candidate | Accepted boundary | Decision still required |
| --- | --- | --- |
| Kernel aggregate evolution | Explicit bootstrap; human Session realization; deterministic association; normalized state plus typed history | Post-Kernel split/merge and automated realization policy |
| Relational store evolution | PostgreSQL normalized state plus typed append-only Kernel history | Backup/restore policy and schemas for future capabilities |
| Packaging asset identity | Completed Media Asset remains production-media completion/readiness authority | Whether a separate Packaging Asset composes a Completed Media Asset/content manifest, and which context owns approval/applicability |
| Post-Kernel Session revision policy | Human completion applies to one package revision; valid late media returns the current package to correction/review | Grace defaults, split/merge, and post-publication behavior |
| Transactional outbox | Required for future externally meaningful durable messages | First consumer, message schema, dispatch/reconciliation ownership |

The documentation-authority decision D-10 is implemented by
[the architecture index](../architecture/README.md), this index, the review/disposition
process, and the plan process. It does not require a duplicate ADR to be effective.
