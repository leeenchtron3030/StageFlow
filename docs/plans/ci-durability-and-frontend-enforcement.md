# CI durability-test enablement, frontend test enforcement, and branch protection

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: Acquisition-style due-diligence audit (2026-08-20, commit `42e71c2`),
  Major finding "CI exists and is green, but nothing actually enforces it"; explicit
  2026-08-21 user directive to proceed with due-diligence remediation as part of
  structural fortification before the DevCon demo.
- Implementation-ready: Yes
- Required escalation or approval, if any: enabling GitHub branch-protection rules is a
  repository-admin setting, not a code change — see Out of scope. Everything else is
  Green: CI-workflow-only, no application dependency/runtime/schema change, reversible.

## Related findings or ADRs

- Finding/disposition: Due-diligence audit Major finding — no branch protection
  (`gh api repos/.../branches/main/protection` → 404), Postgres durability tests skipped in
  CI (`test_durable_event_mode_kernel.py` → 2 skipped, no `STAGEFLOW_TEST_POSTGRES_DSN`),
  frontend job has no `npm run test` step.
- ADR: None required.
- Engineering Directive: ED-0056. Supersedes nothing — the existing [CI quality-matrix
  enforcement](ci-quality-matrix-enforcement.md) plan (ABR-015) explicitly scoped out
  "a frontend test runner" and "services"; this plan closes exactly that deliberate gap
  now that a frontend test runner and durability-relevant Postgres tests both exist.

## Problem statement

The GitHub Actions workflow runs backend and frontend quality checks, but: (1) nothing
requires those checks to pass before a merge, since `main` has no branch protection; (2)
the durability tests covering the new Postgres-backed kernel never actually execute in CI,
because no database service or connection string is configured there — they silently skip;
(3) the frontend test suite (`npm.cmd test`, `node --test ...`) exists and passes locally
but was never added to the CI workflow's frontend job. The riskiest new code path
(durable persistence) and an entire test suite are both currently unexercised by CI.

## Verified current behavior

- `.github/workflows/ci.yml` frontend job runs build/lint/typecheck, no `npm run test`.
- Backend job has no Postgres service; `STAGEFLOW_TEST_POSTGRES_DSN` is unset in CI, so
  durability tests are skipped rather than failing loudly or running for real.
- `gh api repos/leeenchtron3030/StageFlow/branches/main/protection` returns 404 — no
  required status checks, no restriction on force-push or direct pushes to `main`.

## Desired behavior

CI actually gates `main`: a Postgres service runs in the backend job so durability tests
execute for real (not skip); the frontend job runs its existing test suite; and both jobs
are configured as required status checks so a red run blocks merge.

## In scope

- Add a `postgres` service container to the backend CI job with a scoped ephemeral
  database, and set `STAGEFLOW_TEST_POSTGRES_DSN` (or the equivalent variable the test
  suite already reads) so `test_durable_event_mode_kernel.py` and any other
  Postgres-gated tests run for real in CI instead of skipping.
- Add an `npm run test` (or the exact script name in `frontend/package.json`) step to the
  frontend CI job.
- Document (in this plan's completion record and in `.github/workflows/README.md` if one
  exists) the exact required-status-check names so the repository owner can enable branch
  protection referencing them.
- Verify both new CI steps actually pass on a real workflow run (not just local
  reproduction) before marking this plan complete.

## Out of scope

- Enabling GitHub branch protection itself — this is a repository Settings action taken
  by the repository owner (or via `gh api repos/.../branches/main/protection` with admin
  credentials), not a code change Codex should make unilaterally. This plan documents the
  exact check names to protect; the repository owner flips the setting.
- Any new deployment, publishing, secret, or production infrastructure.
- Adding a code-coverage gate (tracked separately as a minor finding).
- Windows CI runners — the existing quality-matrix plan already scoped this out; unrelated
  to this plan.

## Constraints

- Compatibility constraints: the Postgres service must be ephemeral/test-scoped only — no
  connection to any real event data, no production DSN anywhere in workflow files or logs.
- Security and data-handling constraints: the test DSN must not be a secret worth
  protecting (ephemeral CI-local database with a throwaway password) and must never be
  logged in full.

## Implementation approach

1. Add a `services: postgres:` block to the backend CI job (pinned image tag, ephemeral
   credentials, health-checked before tests run).
2. Set the DSN environment variable the existing test suite already expects (confirm the
   exact variable name from `backend/tests/` conftest/fixtures before wiring it — do not
   invent a new one).
3. Add the frontend test step to the existing frontend job, after typecheck/lint and
   before/alongside build, matching how `npm.cmd test` is run in local documentation.
4. Run the workflow (via a scratch PR or the actual plan's own PR) and confirm both new
   steps go green for real, not just skip silently.
5. Record the exact check names (`Backend / Python 3.13`, `Frontend / Node 22`, or their
   post-change equivalents) in the completion record for the repository owner to require.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `.github/workflows/ci.yml` | Add Postgres service + DSN env var to backend job; add test step to frontend job |
| `.github/workflows/README.md` (if present) | Document the new required-check names |
| `docs/plans/README.md` | Add this plan's index row |

## Data or migration considerations

None — CI-only, ephemeral per-run database, no schema or migration change.

## Failure and recovery considerations

If the Postgres service fails to become healthy, the backend job must fail loudly (not
silently skip the durability tests) — a health-check gate before running pytest is
required, not optional.

## Observability requirements

CI run output must make it obvious whether durability tests ran-and-passed versus
skipped, so a future regression here is visible rather than silent.

## Test strategy

- Confirm locally-reproducible Postgres-backed tests pass against the same DSN shape used
  in CI.
- Run the actual GitHub Actions workflow end-to-end (this is validation the plan itself
  requires, not just local commands) and confirm both jobs report the expected step names
  and pass.

## Acceptance criteria

- [ ] Backend CI job runs a Postgres service; durability tests execute and pass (not skip)
  in the real GitHub Actions run.
- [ ] Frontend CI job runs its existing test suite and passes.
- [ ] The plan's completion record names the exact status-check strings for the
  repository owner to mark as required.
- [ ] No production DSN, credential, or real event data appears in workflow files or logs.

## Rollback or reversal

Revert the workflow file changes. No data, schema, or production-infrastructure change to
reverse.

## Open questions

- Confirm the exact environment-variable name the durability tests already expect before
  wiring the CI service (read from `backend/tests/` fixtures, do not guess).

## Completion record

_(To be filled in by whoever implements this plan.)_
