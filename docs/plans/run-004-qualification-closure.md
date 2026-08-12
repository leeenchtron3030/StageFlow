# Run 004 qualification closure and timing telemetry

## Status

Completed

## Execution authority

- **Classification:** Green autonomous.
- **Authority evidence:** The operator-authorized Run 004 closure task, the completed
  Run 004 association investigation, accepted ADR-0023 and ADR-0024, and the repository
  bounded-autonomous-execution policy.
- **Implementation-ready:** Yes. All production Session/media semantics remain fixed;
  the changes are limited to reversible qualification tooling, tests, and sanitized
  documentation.
- **Escalation boundary:** Stop before changing predecessor/successor automatic
  association eligibility, trustworthy-media-time requirements, Session authority,
  persistence, schemas, migrations, or public contracts.

## Objective and acceptance criteria

Close Run 004 as a partial qualification and correct two qualification-only timing
hazards:

1. `StartSession` and `EndSession` capture a timezone-aware timestamp at controller
   entry when `-At now` is requested and forward that explicit value unchanged.
2. Explicit operator-supplied `-At` values remain unchanged and supported.
3. Downstream guards, startup, or runner delay cannot move the captured authority time.
4. `DriveCycles` estimation uses the larger of durable observed media and a shallow,
   metadata-only eligible-source count bounded by the configured source policy.
5. Run 004 is documented as lifecycle/preservation/policy-conformance PASS and
   content-correct automatic turnover association INCONCLUSIVE / NOT QUALIFIED.
6. Focused tests, PowerShell parsing, Ruff, Pyright, documentation checks, and
   `git diff --check` pass.

## Bounded scope

- `scripts/validation/Invoke-StageFlowValidation.ps1` and its runbook.
- Focused controller and qualification-runner tests.
- Sanitized Run 004 result and directly affected validation/plan/project indexes.
- No production code, database, external media, external JSON/summary/environment
  evidence, dependency, schema, migration, frontend, worker, or runtime configuration.

## Implementation approach

1. Capture `UtcNow` immediately after PowerShell parameter binding for human-authority
   Start/End actions whose requested value is `now`; use the captured ISO value only in
   the runner arguments.
2. Retain explicit aware timestamp strings verbatim so the existing runner remains the
   validation boundary.
3. Read only shallow directory-entry metadata for the configured validation source,
   applying the existing extension, hidden-entry, suffix, regular-file, reparse-point,
   and maximum-entry rules. Fall back to durable count if safe source counting is
   unavailable.
4. Record the four-part Run 004 disposition and explicitly defer any different
   predecessor/successor eligibility rule as Yellow.

## Validation strategy

- Controller regressions for Start/End explicit forwarding, entry-time `now` capture,
  downstream delay, and source-aware estimation with ineligible entries excluded.
- Existing qualification-runner timestamp parsing and focused runner/controller suites.
- PowerShell parser validation, Ruff, Pyright, changed-document UTF-8/link checks,
  sensitive-content review, `git diff --check`, and deliberate diff self-review.

## Rollback

Revert the qualification script, focused tests, and documentation. No external evidence
or durable production data requires reversal.

## Completion record

- **Implemented revision:** Working tree based on `74f23b4`; no commit was requested.
- **Files changed:** Qualification controller and focused controller/runner tests; this
  plan, validation plan/index, controller runbook, project brief, and sanitized Run 004
  result. No production code, dependency, schema, migration, database, external media,
  external Run evidence, frontend, worker, or runtime configuration changed.
- **Behavior:** Start/End `-At now` is captured at controller entry and forwarded as an
  explicit aware value; explicit `-At` remains verbatim. DriveCycles telemetry uses the
  larger of durable observed media and a safe bounded shallow eligible-source count.
- **Validation:** 43 focused controller/runner tests passed. Ruff passed. Pyright
  reported zero errors and warnings. PowerShell parsing, strict UTF-8, relative-link
  checks, and `git diff --check` passed. `git diff --check` emitted only existing
  line-ending conversion warnings for unrelated working-tree files.
- **Deviations:** None.
- **Rollback:** Qualification-only changes remain independently reversible.
- **Remaining decision:** Any change to predecessor/successor automatic association
  eligibility remains Yellow and intentionally deferred.
