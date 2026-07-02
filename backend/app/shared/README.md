# Shared

## Purpose

`shared` is reserved for domain-neutral backend building blocks that may be used by bounded contexts.

## What Belongs Here

- Shared errors.
- Shared identifiers.
- Result types.
- Time utilities.
- Domain event primitives after a future directive approves them.

## What Does Not Belong Here

- Context-specific business rules.
- API route definitions.
- FastAPI application setup.
- Database or integration implementation.

## Dependency Rule

`shared` may depend on `core`. It must not depend on `contexts` or `api`.
