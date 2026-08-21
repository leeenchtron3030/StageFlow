# .github/workflows

## Purpose

This directory contains GitHub Actions workflow definitions authorized by accepted
repository authority.

## What Belongs Here

- CI workflows approved by the architecture-baseline disposition or later authority.
- Repository health checks approved by repository authority.
- Deployment workflows only after production infrastructure is formally specified.

## What Does Not Belong Here

- Workflow files created ahead of authorization.
- Docker, deployment, or infrastructure configuration.
- Secrets, tokens, or local machine configuration.

## Current workflow

`ci.yml` runs backend pytest with an ephemeral PostgreSQL 17 service, prints an `app`
coverage report without enforcing a coverage threshold, and runs Ruff/Pyright on Linux.
The frontend job runs the existing Node test suite plus build/lint/typecheck. The exact
status-check names for branch protection are `Backend / Python 3.13` and
`Frontend / Node 22`.

CI does not claim Windows, hardware, or event-operational validation. Deployment and
release automation remain future work requiring separate authority.
