# Changelog

Notable repository changes are recorded here. Dates use the repository merge history;
architecture and validation documents remain the authority for scope and readiness.

## Unreleased - 2026-08-21

### Added

- Shared-secret protection and explicit CORS allow-listing for operational API routers.
- PostgreSQL-backed durability execution and frontend tests in CI, plus backend coverage reporting.
- Sanitized coordinator/startup failure logging and cross-platform qualification-harness gating.

### Changed

- API response mappings are recursively immutable and duplicate route response builders are consolidated.
- Repository orientation, roadmap, environment examples, and governance records reflect current implementation.

## 2026-08-21

- PR #73 added due-diligence remediation plans and resumed Engineering Directive numbering at ED-0055.
- PR #72 added Demo package approval.

## 2026-08-20

- PR #70 added durable Program Expectation reconciliation.

## 2026-08-19

- PRs #63-69 delivered the Demo single-stage slice, hardware-rehearsal tooling, guarded
  rehearsal controller, launch-scoped authority, explicit expectation selection, and
  Devcon publication verification fixes.

## 2026-08-12 through 2026-08-18

- PRs #58-62 delivered Media Timing Evidence and producer UI milestones, producer UX
  refinement, the durable transcription-worker substrate, and local transcription-engine
  qualification.

## Earlier foundation

- PRs #1-57 established the product constitution, architecture and ADR baseline,
  Production-domain contracts and policies, Runtime/Agent foundations, bounded media
  collection, and local-filesystem discovery. See `ENGINEERING_DIRECTIVES.md` and
  `docs/architecture/README.md` for authoritative detail.
