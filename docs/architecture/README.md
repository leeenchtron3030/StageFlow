# StageFlow architecture documentation

## Purpose and scope

This directory is the implementation-facing architecture entry point for StageFlow. It
separates what the repository implements now from accepted architecture, future
direction, and decisions that remain open. It does not replace the Product Constitution,
accepted ADRs, or Engineering Directives.

**Start here:** [StageFlow Master Project Brief](../PROJECT_BRIEF.md)

## Status vocabulary

- **Current implementation:** behavior directly verified in code, configuration, or
  tests at the referenced baseline.
- **Accepted architecture:** a decision approved by the Product Constitution, an
  accepted ADR, or an authoritative disposition. It may not be implemented yet.
- **Future direction:** an accepted destination whose implementation scope and timing
  remain subject to a plan or Engineering Directive.
- **Open decision:** an issue that requires explicit product or architecture judgment.
- **Legacy or superseded:** preserved historical material that is not current authority
  for new work unless a current document explicitly retains it.

Proposed behavior must never be described as current implementation.

## Document index

| Document | Purpose |
| --- | --- |
| [Principles](principles.md) | Accepted durable architectural constraints and current alignment |
| [System context](system-context.md) | Current runtime, actors, data flows, deployment assumptions, and future boundaries |
| [Persistence boundary](persistence.md) | Accepted PostgreSQL authority, implemented ingress/Kernel schema, migration order, and remaining operational gaps |
| [Domain glossary](domain-glossary.md) | Approved qualified terminology, aliases, migration notes, and unresolved terms |
| [Session lifecycle](session-lifecycle.md) | Current Session-related behavior, accepted lifecycle direction, invariants, and open decisions |
| [Segment lifecycle](segment-lifecycle.md) | Current media lifecycle and accepted candidate-to-asset flow |
| [Durable Event-Mode Kernel](durable-event-mode-kernel.md) | Accepted operational slice, current implementation map, and resolved decisions |
| [Durable Kernel operations](durable-kernel-operations.md) | Reference-node configuration, bootstrap, status, recovery, and reversal procedure |
| [ADR index](../adr/README.md) | Accepted decisions, historical ADRs, and unresolved ADR candidates |
| [Review index](../reviews/README.md) | Evidence reviews and authoritative dispositions |
| [Plan index](../plans/README.md) | Implementation planning process and template |

Foundational and historical sources remain in place:

- [Product Constitution](../../PRODUCT_CONSTITUTION.md)
- [ADR-0001 through ADR-0018](../../ARCHITECTURE_DECISIONS.md)
- [Engineering Directive index](../../ENGINEERING_DIRECTIVES.md)
- [Foundational glossary](../00_Glossary.md)
- [Domain model](../00.5_Domain_Model.md)
- [Architecture layers](../03.6_Architecture_Layers.md)
- [Bounded contexts](../04.5_Bounded_Contexts.md)
- [Integration architecture](../04.6_Integration_Architecture.md)
- [Reasoning model](../05_Reasoning_Model.md)

Older documents remain useful evidence and design history. Their broad V1 descriptions
must not be read as proof that a component is implemented. Where their language conflicts
with an accepted disposition or newer accepted ADR, use the current qualified language
in this directory and record any required compatibility work.

## Authority and precedence

1. The [Product Constitution](../../PRODUCT_CONSTITUTION.md) is the foundational product
   and engineering authority.
2. Accepted ADRs record durable architectural decisions.
3. An approved review disposition determines which review findings or recommendations
   have authority; a review alone does not.
4. The documents in this directory synthesize those accepted decisions and verified
   current behavior.
5. [Engineering Directives](../../ENGINEERING_DIRECTIVES.md) authorize bounded
   implementation scope. They do not silently revise higher-level architecture.
6. Implementation plans explain how approved work will be delivered. A plan does not
   approve an unresolved architecture decision.

Code and tests are authoritative evidence of current behavior, not independent authority
for intended architecture. If authorities appear to conflict, do not resolve the conflict
silently: document it and obtain an explicit decision.

## Changing architecture

1. Verify current behavior and identify the affected principle, term, lifecycle, or
   boundary.
2. Determine whether an accepted decision already governs the change.
3. Use an ADR for a durable decision with meaningful alternatives or consequences.
4. Obtain disposition or approval before treating a review recommendation as accepted.
5. Create an implementation plan for cross-module, migration-bearing, operational, or
   otherwise high-risk work.
6. Implement only through an approved, bounded task or Engineering Directive.
7. Update the architecture index, glossary/lifecycle documents, ADR index, and completion
   record as applicable.

Historical reviews, ADRs, and completed plans remain available. Supersession is explicit;
documents are not rewritten to imply that earlier architecture always matched the present.
