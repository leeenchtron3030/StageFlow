# ADR-0026: Policy-scoped automatic authority

## Status

Accepted

Accepted 2026-08-28. Acceptance establishes the authority boundary, the policy modes, and
the required audit lineage. It activates no automation: every mode remains configured
independently per decision type, Event/deployment, and version, and existing human-only
Kernel commands gain no automatic authority from this acceptance.

## Date

2026-08-09

## Context

StageFlow begins with human authority for consequential Session, package, editorial, and
delivery decisions. The Product Constitution requires explainability, visible reasoning,
human editorial authority, and findings before actions. The Kernel implements human
Session realization/boundary/package decisions and a narrowly deterministic media
association policy with explicit provenance.

Future operation may benefit from progressively automating well-understood decisions,
such as qualified deterministic association or Assembly approval. A single global
automation switch would erase different risk, evidence, and authority requirements.
Model confidence alone cannot determine whether StageFlow may act. Historical agreement
with humans is useful eligibility evidence but cannot silently grant StageFlow more
authority.

The decision is Yellow because it governs how machine/deterministic outputs can produce
authoritative state across multiple bounded contexts.

## Decision

If accepted, StageFlow will evaluate consequential automation as:

```text
Evidence -> versioned scoped Policy -> Authority disposition -> Decision
```

Evidence records what is known, contradictory, absent, inferred, stale, or unavailable.
Policy determines whether those inputs satisfy explicitly configured requirements.
Authority disposition determines whether StageFlow may auto-authorize, may only propose,
requires human action, or must block/defer.

### Policy identity, scope, and activation

Every automation policy has stable identity, version, decision type, Event/deployment
scope, evidence and freshness requirements, contradiction/missing-dependency behavior,
mode, effective interval, and activation record. Activation identifies the human or
configuration authority, activation time, and exact version/scope.

Modes are independent per decision type:

- `manual`: only a human can decide;
- `assisted`: StageFlow may propose; a human confirms or changes;
- `exception_only`: explicitly qualified cases may be automatically authorized and all
  exceptions go to human review; and
- `automatic`: broader authority for that named decision type under the activated
  policy, while all safety gates and provenance requirements remain.

Session start, Session end, media association, package completion, Assembly approval,
rendering authorization, and future publishing are separate decision types. There is no
global `automation=true` and no implicit inheritance of authority across types.

### Authority evaluation

Policy may use deterministic invariants, evidence completeness/contradiction, model and
policy versions, model confidence, historical validation, dependency health,
reconciliation freshness, and Event configuration. Model confidence may influence
eligibility but cannot be the sole source of automatic authority.

Evaluation is deterministic for a fixed policy version and fixed input references. It
returns a categorical authority disposition, stable reason codes, input references and
revisions, and freshness/exception details. The domain command that owns the resulting
state still validates its own invariants and revision.

### Trust progression

StageFlow may compute reviewed-proposal counts, unchanged acceptance rate, correction
rate, boundary-adjustment rate, and association-correction rate as decision-support
evidence. It never self-activates a stronger policy or mode. A human/configuration
authority must explicitly activate every increase in automatic authority and may
deactivate or narrow it.

### Decision provenance and correction

Every automatic authoritative decision durably records:

- policy identity/version, activation identity, scope, and decision type;
- evidence/input identities and revisions considered;
- relevant model identity/version when applicable;
- evaluated and decided times;
- categorical reasons human review was not required;
- resulting authoritative subject/state revision; and
- correlation/operation identity for replay and reconciliation.

Human override or correction appends a new decision and preserves the earlier automatic
decision. Full event sourcing is not required; current state plus typed append-only
decision/activation history is sufficient.

The Producer Work Queue receives required-human, withheld, stale, contradiction, and
policy/configuration exception outcomes. Ordinary machine suggestions do not become
Producer work merely because they exist.

## Alternatives

### Keep every decision permanently manual

This maximizes direct human control and remains a valid policy mode, but it prevents
explicitly qualified low-risk automation at scale. Rejected as the only architecture;
manual remains the default and a supported per-type mode.

### One global automation level or Boolean

Simple to configure but unsafe because Session boundaries, media association, Assembly,
rendering, and publishing have different evidence and consequence. Rejected.

### Let model confidence cross a threshold

Easy to implement, but confidence is model-specific, may be poorly calibrated, ignores
contradictory/missing/stale evidence, and cannot grant product authority. Rejected.

### Automatically increase authority from historical performance

Could reduce configuration effort but would allow StageFlow to change its own trust
boundary silently. Rejected. Metrics are advisory evidence only.

### Hard-code automation rules inside each command

This keeps implementation local but obscures policy identity/version/activation and
makes cross-context audit inconsistent. Rejected for authority selection. Domain commands
still own final invariant validation.

## Consequences

### Positive

- Human authority remains explicit while allowing measured, decision-specific progress.
- Every automatic action is reproducible and explainable from policy and input lineage.
- Contradiction, staleness, and dependency health can block authority even when a model
  is confident.
- Automation can be activated, narrowed, or deactivated per Event/deployment and
  decision type without changing domain semantics.
- Prior automatic decisions and later human corrections remain historically visible.

### Negative and risks

- Policy versioning, activation, evaluation, and audit records add durable schema and UI
  requirements.
- Poorly designed policy scopes can still grant unintended authority; activation needs
  validation and least-authority defaults.
- Eligibility metrics can be misleading without representative reviewed samples.
- Cross-context reason codes and freshness semantics require careful standardization.
- Existing Kernel human-only commands do not become automatic until a later bounded plan
  explicitly integrates one decision type.

## Validation

Acceptance and implementation plans must require:

- decision-type and Event/deployment scope isolation;
- stable policy identity/version and explicit activation/deactivation history;
- manual, assisted, exception-only, and automatic disposition behavior;
- missing, contradictory, stale, unhealthy-dependency, and reconciliation-not-fresh
  fail-closed cases;
- proof that confidence alone cannot grant authority;
- proof that performance metrics cannot self-activate a policy;
- exact/conflicting replay, stale subject revision, and concurrent evaluation/command
  handling;
- complete automatic-decision provenance and preservation after human correction;
- bounded Work Queue projections for withheld/exception outcomes; and
- explicit PostgreSQL forward/reversal, recovery, and audit-history preservation tests.

## Related documents

- [Post-Kernel capability layer](../architecture/post-kernel-capability-layer.md)
- [Post-Kernel capability implementation plan](../plans/post-kernel-capability-layer.md)
- [ADR-0009: Verification preserves reasoning history](../../ARCHITECTURE_DECISIONS.md)
- [ADR-0023: Session authority and completion](ADR-0023-session-authority-and-completion.md)
- [ADR-0024: Durable Kernel authority and persistence](ADR-0024-durable-kernel-authority-and-persistence.md)
- [Domain glossary](../architecture/domain-glossary.md)
