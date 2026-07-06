# Shared

## Purpose

`shared` contains frontend contract primitives that are independent of a specific workflow.

These contracts mirror the backend shared language conceptually. They are not physically shared packages, and they do not connect to backend APIs.

## What Belongs Here

- Generic identifiers such as `EntityId` and `CorrelationId`.
- Result and error primitives.
- Clock, timestamp, and time range helpers.
- Base domain event shapes.
- Future framework-neutral utilities approved by Engineering Directives.

## What Does Not Belong Here

- Workflow-specific behavior.
- Backend data-fetching implementations before integration is approved.
- Domain business logic.
- Database-entity-oriented feature models.

## Core vs Shared

`core` is for application-wide frontend setup such as providers and configuration.

`shared` is for small reusable contract language used by workflow code once future directives add it.

## Adding Shared Primitives

Add a new shared primitive only when multiple workflows or frontend layers need the same generic concept. Do not add business-specific concepts here.

## Expected Future Directives

- ED-0004 adds the initial shared contract primitives.
- Future frontend directives may add shared utilities once concrete workflow needs exist.
