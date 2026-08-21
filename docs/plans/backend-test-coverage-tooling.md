# Backend test coverage tooling

## Status

Completed

## Execution authority

- Classification: Green autonomous
- Authority evidence: ED-0061 and the explicit 2026-08-21 implementation request.
- Implementation-ready: Yes
- Required escalation or approval, if any: None.

## Related findings or ADRs

- Finding/disposition: Due-diligence coverage-tooling residue.
- ADR: None required.
- Engineering Directive: ED-0061.

## Problem statement and verified behavior

Backend CI runs pytest but does not measure or display coverage. `backend/pyproject.toml` and `uv.lock` contain no `pytest-cov` tooling.

## Desired behavior and scope

Add bounded development-only `pytest-cov` tooling, lock it, and print a deterministic `app` terminal coverage report in CI. Do not set a coverage threshold, upload to a third party, exclude modules to inflate results, or change production dependencies.

## Dependency and compatibility considerations

`pytest-cov` and Coverage.py are permissively licensed development tools with no production import, event-runtime, schema, migration, configuration, or offline-operation effect.

## Implementation approach and affected files

Update `backend/pyproject.toml`, regenerate `backend/uv.lock`, update `.github/workflows/ci.yml`, and document reporting in `.github/workflows/README.md`. Revert all four together for rollback.

## Test strategy and acceptance criteria

- `uv sync --dev --locked` succeeds.
- `uv run pytest --cov=app --cov-report=term-missing` prints coverage and retains ordinary pytest pass/fail semantics.
- Ruff and Pyright pass.
- No `--cov-fail-under` is configured.

## Open questions

None.

## Completion record

Implemented 2026-08-21.

- Added development-only `pytest-cov`/Coverage.py tooling and lockfile entries.
- CI now runs `pytest --cov=app --cov-report=term-missing` with branch coverage enabled and
  no failure threshold or third-party upload.
- `uv sync --dev --locked` passed; the full run reported 87% total coverage with 1,796
  tests passed and five PostgreSQL-qualified tests skipped locally.
- No production dependency or runtime configuration changed.
