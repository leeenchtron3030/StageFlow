# Shared

## Purpose

`shared` contains domain-neutral backend contract primitives that may be used by bounded contexts.

These contracts define common language for identifiers, results, errors, time, correlation, and base domain events. They are intentionally small and generic.

## What Belongs Here

- Generic identifiers such as `EntityId` and `CorrelationId`.
- Explicit `Result` values for expected success/failure flow.
- Structured `StageFlowError` categories.
- Clock, timestamp, and time range contracts.
- Base `DomainEvent` contracts.

## What Does Not Belong Here

- Context-specific business rules.
- API route definitions.
- FastAPI application setup.
- Database or integration implementation.
- Domain-specific identifiers such as session, clip, or package IDs.
- Business-specific domain events.

## Core vs Shared

`core` contains backend process concerns such as configuration, logging, health, and lifecycle.

`shared` contains reusable contract language that bounded contexts can depend on without importing from each other.

## Adding Shared Primitives

Add a new shared primitive only when it represents generic language needed across multiple bounded contexts or layers.

Do not add business logic to `shared`. Bounded contexts will use these primitives to express StageFlow behavior later.

## Dependency Rule

`shared` may depend on `core`. It must not depend on `contexts` or `api`.
