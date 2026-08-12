# Durable Event-Mode Kernel Green follow-up closure evidence

**Closure date:** 2026-08-09

**Implementing baseline:** `708f446` (`main`)

**Implementation commits:** `a31edee` (migration/replay) and `2576b5f`
(startup/status), preceded by `6f77235` (verification artifact and implementation plan)

**Review mode:** Green implementation closure plus deliberate final diff/self-review.
This is not a new independent phase review and does not alter the authority of the
targeted independent correction verification.

**Final recommendation:** **ACCEPT DKV-001 THROUGH DKV-004 AS CLOSED**

The targeted independent verification already recommended **ACCEPT WITH GREEN
FOLLOW-UP**. The four named follow-ups are now implemented, covered by focused and full
real-PostgreSQL validation, and reflected in current-facing documentation. The Durable
Event-Mode Kernel can be recorded as StageFlow's completed bounded operational
foundation. This is not production readiness, event readiness, deployment approval, or
reference-node certification.

## Scope and authority

This closure is governed by ADR-0022 through ADR-0024, the accepted Durable Event-Mode
Kernel architecture, DKV-001 through DKV-004 in the
[targeted verification](durable-event-mode-kernel-correction-verification.md), and the
[Green closure plan](../plans/durable-event-mode-kernel-green-follow-up-closure.md).
The task remained Green: it introduced no new product semantics, infrastructure service,
dependency, trust boundary, public compatibility break, destructive data migration, or
deployment action.

In scope were one additive migration, durable replay-result preservation, startup/status
truth, focused tests, current-facing documentation, and closure evidence. No production
data, credentials, source media, machine policy, external service, dependency manifest,
lockfile, frontend source, or deployment configuration was changed.

## Finding dispositions

| Finding | Disposition | Closure evidence |
| --- | --- | --- |
| DKV-001 | **CLOSED** | Migration `0005_kernel_follow_up_closure` reconstructs legacy reopened completion membership only from the latest association history strictly before completion, tags the reconstructed rows, and classifies relevant equal-time history as unresolved without inserting membership. Real PostgreSQL tests cover both cases, reversal, repeated reversal, reapply, ledger state, and provenance. |
| DKV-002 | **CLOSED** | New Session start, boundary-correction, and package-completion commands store a versioned original Session result in the human-command ledger in the same transaction. Immediate and delayed replay from a fresh repository returns the original result after later boundary/package changes; mismatched operation reuse remains a typed conflict. Pre-`0005` rows without a trustworthy snapshot retain the explicit legacy current-row fallback rather than fabricated history. |
| DKV-003 | **CLOSED** | Process-local startup progress separately records configuration supplied/valid, PostgreSQL availability, and Runtime composition. The additive status response preserves those facts alongside existing source availability and readiness. Tests cover no config, invalid supplied config, valid config with PostgreSQL unavailable, source failure, successful real-PostgreSQL startup, and recovery. |
| DKV-004 | **CLOSED** | The Project Brief, principles, Kernel architecture, persistence/operations guidance, review index, and plan index now describe the implemented bounded Kernel, migrations through `0005`, accepted configuration boundary, and status behavior without inflating readiness. Historical reviews remain unchanged. |

## Migration and data behavior

The forward migration is additive and ledger-guarded:

- `human_command_idempotency.result_snapshot` stores a versioned JSON Session result for
  new consequential Session commands;
- `session_completion_history.membership_snapshot_status` distinguishes `recorded`,
  `reconstructed`, and `unresolved`, with a required reason for non-recorded states;
- `session_completion_asset.snapshot_origin` distinguishes ordinary membership from
  rows reconstructed by `0005`;
- only latest strictly-prior association history is eligible for reconstruction; and
- a relevant equal-time association decision makes the snapshot unresolved, producing no
  invented membership.

The reverse migration deletes only rows tagged `legacy_reconstructed_0005`, drops the
additive constraints/columns, and removes only the `0005` ledger row. It leaves `0001`
through `0004` and their identities/lineage intact. Reversal is safely skipped when the
`0005` ledger row is absent. The real migration test reversed twice, observed four
remaining ledger versions and no reconstructed row/snapshot column, then reapplied and
reconstructed the same unambiguous membership.

## Replay behavior

The PostgreSQL adapter now stores the original Session returned by Session start,
boundary correction, and package completion before the command transaction commits.
Replays first verify command kind and request digest, then use that immutable result
snapshot. Historical decision identity remains in its typed history table. Media
assignment replay continues to reconstruct its exact history row and was not broadened.

The real delayed-replay test applies later boundary and package changes, creates a fresh
repository/kernel instance, and verifies that all three original Session results replay
exactly. A changed completion request using the same operation ID remains fail-closed
with `human_command_operation_id_conflict`.

## Startup and status truth

The lifecycle retains `KernelStartupProgress` even when composition fails. The status
boundary can now distinguish:

- no supplied configuration;
- supplied but invalid configuration;
- supplied and valid configuration with PostgreSQL unavailable;
- valid configuration and available PostgreSQL before Event/Runtime composition;
- composed Runtime with a failed source reconciliation; and
- composed, dependency-available, operationally ready state after recovery.

Existing `configured`, `database_available`, per-Stage `source_available`, and `ready`
meanings remain available. The additive fields are `configuration_supplied`,
`configuration_valid`, and `runtime_composed`. DSNs and source paths remain absent from
responses.

## Validation matrix

All commands ran on Windows from the repository workspace. Real database tests used a
new empty database, `stageflow_followup_full`, in a disposable loopback PostgreSQL 17.10
cluster with a synthetic trust-only test role.

| Gate | Result |
| --- | --- |
| Focused migration/replay static and real-PostgreSQL tests | **PASS** — forward/reverse/reapply, unambiguous and equal-time cases, delayed/fresh-process replay, and conflict checks passed |
| Focused startup/status suite with real PostgreSQL | **PASS** — 13 passed, 1 existing warning |
| Full backend pytest with fresh real PostgreSQL | **PASS** — 1,622 passed, 5 skipped, 1 warning in 12.87s |
| Ruff | **PASS** — all checks passed |
| Pyright | **PASS** — 0 errors, 0 warnings, 0 informations |
| Clean frontend `npm ci` | **PASS** — 592 packages installed from the lockfile |
| Frontend build | **PASS** — Next.js 16.2.10 optimized static build |
| Frontend lint | **PASS** |
| Frontend typecheck | **PASS** — `tsc --noEmit` |
| Repository whitespace check | **PASS** — final documentation working tree clean under `git diff --check` |

The five backend skips are existing platform/capability exclusions: three Windows
symlink-privilege cases, one non-portable FIFO case, and one POSIX descriptor-bound
`scandir` case. The warning is the existing Starlette `TestClient`/httpx deprecation.

The first sandboxed focused Ruff/Pyright attempt could not execute/read virtual-
environment tools; the approved rerun passed. The first frontend command selected
`npm.ps1` and was blocked by the machine's PowerShell script policy; the same matrix
rerun through the portable Node `npm.cmd` completed successfully.

Clean `npm ci` reported 12 audit findings (3 moderate, 9 high). No audit fix, dependency
update, manifest change, or lockfile change was authorized or performed.

## Deliberate diff/self-review

The final review checked migration ordering and transactional application, legacy-data
selection, equal-time ambiguity, FK-preserving identity/lineage, reversal selectivity,
repeated reversal, replay conflict ordering, transaction ownership of result snapshots,
legacy fallback truthfulness, status compatibility/redaction, architecture containment,
and documentation claims.

No Critical, High, Medium, or Low in-scope defect remains. No Yellow or Red condition was
found. The implementation stays inside the modular monolith, uses direct synchronous
domain calls, keeps PostgreSQL authoritative, and does not add a broker, worker system,
generic event store, or continuous watcher.

## Acceptance recommendation

## ACCEPT

DKV-001 through DKV-004 are closed. The targeted independent verification's Green
conditions are satisfied, so the Durable Event-Mode Kernel may be recorded as the
completed bounded operational foundation.

Production deployment, destructive production-data action, conference-duration
qualification, real recorder/livestream coexistence, event-node power remediation, and
event-readiness review remain separate future gates.
