# CI enforcement of the verified quality matrix

## Status

Completed — independent review accepted

## Execution authority

- Classification: Green autonomous
- Authority evidence: ABR-015 existing-quality-matrix disposition, accepted for
  immediate implementation.
- Implementation-ready: Yes
- Required escalation or approval, if any: None.

## Related findings or ADRs

- Finding/disposition: ABR-015 — existing quality matrix accepted for immediate CI.
- ADR: None required.
- Engineering Directive: None; the later accepted disposition supersedes the empty
  scaffolding's outdated statement that a future directive is still required.

## Problem statement

The repository documents six verified backend/frontend quality commands but has no CI
workflow to enforce them. Existing `.github` documentation still describes workflows as
future work.

## Intended outcome

A GitHub Actions workflow runs on Linux for pull requests and pushes to `main`, with
independent backend and frontend jobs:

- backend: `uv sync --dev`, pytest, Ruff, and Pyright on Python 3.13;
- frontend: `npm ci`, build, lint, and typecheck on an explicitly selected supported
  Node LTS release.

The workflow and documentation explicitly avoid claiming event-operational readiness.

## Scope and non-goals

- Add one validation-only workflow and update directly affected repository docs.
- Do not add deployment, publishing, secrets, services, a frontend test runner, or a
  repository-wide formatter.
- Do not claim Windows support from a Linux-only runner.

## Compatibility, dependencies, and rollback

This adds development automation only. Standard GitHub Actions are CI tooling, not
production dependencies; application lockfiles, schemas, migrations, and runtime
configuration remain unchanged. Rollback is the isolated workflow/documentation revert.

## Validation

- Inspect workflow syntax and command parity with `AGENTS.md`/package manifests.
- Run every configured command locally when tooling is available.
- Run `git diff --check`.

## Completion record

- Files and migrations actually changed: added `.github/workflows/ci.yml`; updated
  `.github/README.md`, `.github/workflows/README.md`, `REPOSITORY_MANIFEST.md`, and the
  project brief. No application dependency, lockfile, schema, migration, deployment,
  secret, or runtime configuration changed.
- Commands and tests actually run: verified pinned action tags against their upstream
  repositories; reviewed workflow command parity and least-privilege settings; ran the
  full available backend matrix and `git diff --check`; checked local Node/npm
  availability.
- Results and warnings: backend pytest passed 1,543 tests with 5 expected platform
  skips and one existing Starlette/httpx deprecation warning; Ruff and Pyright passed;
  `git diff --check` found no whitespace errors and only LF-to-CRLF conversion warnings.
  Node and npm are unavailable on this host, so frontend build, lint, and typecheck were
  not run locally; the new Linux CI job enforces all three. No `actionlint` or other
  repository workflow validator is configured.
- Execution authority used: Green autonomous.
- Approved deviations: None.
- Rollback status: Not needed.
- Independent review: accepted with no actionable findings after action pinning,
  `persist-credentials: false`, command-parity, and documentation corrections.
- Remaining work: observe the first GitHub-hosted run after publication; that external
  run is operational confirmation, not an implementation blocker.
