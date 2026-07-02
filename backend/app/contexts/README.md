# Contexts

## Purpose

`contexts` contains StageFlow bounded context packages.

## What Belongs Here

- Identity & Access.
- Event Management.
- Production.
- Editorial.
- Media Rendering.
- Packaging & Delivery.
- Publishing & Analytics.
- Integration.
- Simulation.

## What Does Not Belong Here

- FastAPI application setup.
- Generic shared primitives.
- Database schema or external adapters before future directives approve them.
- Cross-context shortcuts that bypass the architecture.

## Dependency Rule

Contexts may depend on `shared` and `core`. Contexts must not depend on `api`.

ED-0002 creates package boundaries only. No bounded-context behavior is implemented.
