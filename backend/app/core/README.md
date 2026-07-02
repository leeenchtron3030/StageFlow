# Core

## Purpose

`core` contains backend process concerns that sit below the domain-oriented packages.

## What Belongs Here

- Configuration loading.
- Application lifecycle hooks.
- Logging setup.
- Low-level health wiring that does not depend on domain behavior.

## What Does Not Belong Here

- StageFlow business rules.
- Bounded context implementation.
- API route orchestration beyond infrastructure-level concerns.
- Database, worker, media, or integration implementation before future directives approve them.

## Dependency Rule

`core` must not import from `shared`, `contexts`, or `api`.
