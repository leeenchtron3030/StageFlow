# Frontend dependency security remediation

## Status

Approved

## Execution authority

- Classification: Green autonomous
- Authority evidence: Acquisition-style due-diligence audit (2026-08-20) Minor finding
  "no coverage tool configured" section context and the completed [Producer UX
  operational refinement](producer-ux-operational-refinement.md) plan's own explicit
  scope note: "Compatible patch-level Next.js maintenance within the existing major/minor
  line if install, build, tests, and audit evidence remain clean." That plan flagged 12
  audit findings without fixing them ("no audit fix has been run"); this plan is the
  scoped follow-up it deferred. [ED-0066's dependency/license
  report](dependency-license-sbom-2026-08-21.md) separately flagged the
  `@tailwindcss/oxide-wasm32-wasi`/`@emnapi/*` lockfile version mismatch that fails npm's
  native `npm sbom` command as a "Frontend owner" follow-up item. Explicit 2026-08-22
  user directive to queue independent new-capability/hygiene work while ED-0067/ED-0068
  are in progress.
- Implementation-ready: Yes
- Required escalation or approval, if any: None. Every candidate fix stays within
  `next`'s existing declared `^16.2.11` semver range (resolves to `16.3.2`, same major
  version) and no other change requires `--force` or a major-version jump. If any
  individual finding turns out to require `--force` or a breaking bump by the time this is
  implemented (registry state can shift), stop and report that specific package rather
  than forcing it through.

## Related findings or ADRs

- Finding/disposition: `npm audit` on `frontend/` currently reports 11 vulnerabilities (2
  moderate, 9 high) across `@hono/node-server`, `brace-expansion`, `ip-address`,
  `js-yaml`, `nanoid`, `postcss` (direct and via `next`), `sharp` (via `next`), and
  `undici` — all transitive, all with `fix available via npm audit fix` (no `--force`
  needed). `npm audit fix --dry-run` confirms the resulting change set: `next`
  16.2.11 → 16.3.2 (within its existing `^16.2.11` range), `sharp` 0.34.5 → 0.35.3,
  `postcss` 8.5.16 → 8.5.23 (plus removal of a stale nested `postcss` 8.4.31), and several
  transitive dev-tooling bumps (`undici`, `nanoid`, `js-yaml`, `ip-address`, `hono`,
  `fast-uri`, `brace-expansion`, `@swc/helpers`). One `npm warn allow-scripts` notes
  `unrs-resolver@1.12.2` has a pending, not-yet-reviewed install script.
- ADR: None required — dependency version bumps within existing declared ranges, no new
  dependency, no schema/runtime change.
- Engineering Directive: ED-0069.

## Problem statement

Both the due-diligence audit and the completed Producer UX plan flagged these findings
without remediating them, deliberately deferring "dependency remediation" until it was
"explicitly scoped." This plan is that explicit scope: fix what's mechanically fixable
now, verify nothing regresses, and leave anything that would require a forced/breaking
change for a separately scoped decision.

## Verified current behavior

- `frontend/package.json` pins `"next": "^16.2.11"` — the `16.3.2` resolution from `npm
  audit fix` is within this existing declared range; no `package.json` range edit is
  needed, only the lockfile updates.
- `npm ls @emnapi/core @emnapi/wasi-threads` on this Windows machine reports neither
  package installed — the `@tailwindcss/oxide-wasm32-wasi` optional WASI variant is
  platform-skipped here, so the lockfile version mismatch ED-0066 found does not affect
  this machine's actual installed tree; it only affects lockfile-only tooling (`npm
  sbom --package-lock-only`) that reads the full multi-platform graph.
- No forced/breaking change appears in the current `npm audit fix --dry-run` output.
  Registry state can change before implementation; re-run the dry-run first and stop if a
  new finding requires `--force`.

## Desired behavior

`npm audit` reports zero vulnerabilities (or the smallest remaining set that genuinely
requires a forced/breaking change, explicitly called out rather than silently left). The
`@tailwindcss/oxide-wasm32-wasi` optional dependency's declared `@emnapi/*` version
requirements are reconciled with what the lockfile actually resolves, so `npm sbom
--package-lock-only` runs without `ESBOMPROBLEMS`. The full frontend quality suite
(build/lint/typecheck/test) remains clean after the update.

## In scope

- Run `npm audit fix` (no `--force`) and commit the resulting `package-lock.json` change.
- Reconcile the `@emnapi/core`/`@emnapi/wasi-threads` optional-dependency version mismatch
  flagged by ED-0066, if doing so doesn't itself require forcing an unrelated breaking
  change — confirm `npm sbom --package-lock-only` succeeds afterward as the acceptance
  signal.
- Review the `unrs-resolver@1.12.2` pending install-script notice
  (`npm audit signatures`/`npm query`/reading its postinstall script) and either approve it
  explicitly via the existing `allow-scripts` mechanism or leave it deliberately pending
  with a documented reason — do not blanket-allow all pending scripts.
- Re-run the full frontend quality suite after the dependency change and fix any surfaced
  regression that is clearly caused by this change; if a regression isn't obviously caused
  by this change, stop and report rather than guessing at an unrelated fix.

## Out of scope

- Any dependency requiring `--force` or a major-version bump — if the dry-run shows one
  by implementation time, document it and stop rather than forcing it through.
- Any new dependency, feature, or unrelated `package.json` edit.
- Backend dependency changes (already covered separately by ED-0066's investigation; no
  backend dependency change was authorized there either).
- Any change to `frontend/src/` application code beyond what's strictly required to fix a
  regression this exact dependency bump caused.

## Constraints

- Compatibility constraints: stay within `next`'s already-declared `^16.2.11` range; do
  not widen or change any `package.json` version constraint as part of this plan.
- Security/data-handling constraints: do not blanket-approve pending install scripts
  without reviewing what they do.

## Implementation approach

1. Re-run `npm audit fix --dry-run` immediately before starting, to confirm the change set
   still matches what's documented here (registry state may have shifted).
2. Run `npm audit fix` for real; confirm `npm audit` reports zero remaining findings (or
   document exactly which remain and why they weren't forced).
3. Investigate and reconcile the `@emnapi/*` version mismatch; confirm `npm sbom
   --package-lock-only` succeeds.
4. Review the `unrs-resolver` pending install script; approve or document why it stays
   pending.
5. Run the full frontend quality suite; fix any regression clearly caused by this change,
   otherwise stop and report.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `frontend/package-lock.json` | Dependency version bumps from `npm audit fix` plus the `@emnapi/*` reconciliation |
| `frontend/package.json` | Only if `npm audit fix` needs a compatible range widening within the same major version — otherwise unchanged |
| `docs/security/dependency-license-sbom-2026-08-21.md` (or a short follow-up note) | Record that the ED-0066 lockfile-integrity follow-up item is closed, with the new `npm sbom` result |

## Data or migration considerations

None.

## Failure and recovery considerations

Not applicable beyond standard dependency-update verification — no runtime failure/recovery
behavior changes.

## Observability requirements

Not applicable.

## Test strategy

- `npm audit` reports zero vulnerabilities (or an explicitly documented remainder).
- `npm sbom --package-lock-only` succeeds without `ESBOMPROBLEMS`.
- `npm.cmd test`, `npm.cmd run lint`, `npm.cmd run typecheck`, `npm.cmd run build` all
  pass.
- `git diff --check`.

## Acceptance criteria

- [ ] `npm audit` reports zero vulnerabilities, or every remaining one is explicitly
  documented with the reason it wasn't forced.
- [ ] `npm sbom --package-lock-only` succeeds (the `ESBOMPROBLEMS` lockfile-integrity
  issue ED-0066 flagged is resolved).
- [ ] The `unrs-resolver` pending install-script notice is explicitly reviewed and either
  approved or documented as deliberately pending.
- [ ] Full frontend quality suite (test/lint/typecheck/build) passes.
- [ ] No `package.json` version constraint widened beyond what was already declared,
  except where genuinely required and documented.

## Rollback or reversal

Revert `package-lock.json` (and `package.json` if touched). No application code, schema,
or runtime configuration to reverse.

## Open questions

- None blocking. If registry state has shifted by implementation time such that a fix now
  requires `--force`, stop and report that specific package rather than proceeding.

## Completion record

_(To be filled in by whoever implements this plan.)_
