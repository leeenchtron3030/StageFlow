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

`ci.yml` runs backend pytest/Ruff/Pyright and frontend build/lint/typecheck on Linux.
It does not run a frontend test suite because none is configured, and it does not claim
Windows or event-operational validation. Deployment and release automation remain future
work requiring separate authority.
