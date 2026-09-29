# Changelog

Notable repository changes are recorded here. Dates use the repository merge history;
architecture and validation documents remain the authority for scope and readiness.

## Unreleased

- ED-0102 repository cleanup: current-state documentation corrections, merge-history changelog, Unicode generator line wrapping, the Next 16 `proxy.ts` rename, and the re-render quality-reason `aria-describedby` association.

## 2026-09-28

- PR #140 added Assembly approval items to the Producer Work Queue (ED-0101).
- PR #139 approved the Assembly Work Queue and repository cleanup plans (ED-0101, ED-0102).
- PR #138 refined Render quality presentation, provenance, re-render reasoning, and the AAC upper-bound label (ED-0100).

## 2026-09-27

- PRs #136-137 added Event render quality settings and recorded Run 004, including the native AAC bitrate undershoot (ED-0099).
- PRs #133-135 approved the audio/quality plans, added render profile v3 audio, and fixed exact audio lengths with Run 003 evidence (ED-0098, ED-0099).
- PRs #130-132 planned and implemented backend and frontend hardening, including worker recovery, media format allowlists, Host-header checks, Unicode drift detection, and render chronology (ED-0096, ED-0097).
- PR #129 added the Editorial review surface, phrase-list publishing, and derivation actions (ED-0095).
- PRs #127-128 planned and added Producer Assembly and render actions with capability command audit logging (ED-0094).
- PRs #125-126 planned the Producer outputs UI and added its access foundation and read-only Session outputs (ED-0093).
- PR #124 added deterministic transcript phrase-match Editorial candidates with provenance and unchanged human review authority (ED-0092).

## 2026-09-26

- PR #123 approved the derived Editorial candidate implementation plan (ED-0092).
- PRs #121-122 planned and added advisory Media Timing Evidence as an Assembly ordering source (ED-0091).
- PRs #119-120 planned and added production media timing inspection through an operator-installed ffprobe worker (ED-0090).
- PRs #116-118 planned and added Assembly media-order fallback, frozen render slot order, and constant-frame-rate render profile v2 (ED-0088, ED-0089).
- PR #115 implemented the first durable render operation, NVENC adapter, render worker, and bounded APIs (ED-0087).

## 2026-09-25

- PR #114 accepted the render-operation ADR and implementation plan (ED-0087).
- PR #113 added human Session-local Assembly metadata overrides with frozen provenance (ED-0086).
- PR #112 added the multi-encode benchmark and recorded the reference GPU's aggregate throughput limit (ED-0085).
- PR #111 added neutral Demo program-source fields with deprecated compatibility aliases (ED-0084).
- PR #110 corrected validation-controller console encoding for Windows turnover checkpoints (ED-0083).
- PR #109 reconciled current-state documentation after the Demo 2 merge (ED-0082).
- PR #108 added roadmap-scout and directive tooling.
- PRs #107 and #71 planned and merged the generalized Autonomous Event Node and coordinator safety net (ED-0063, ED-0081).
- PRs #101-102 and #106 refined the benchmark corpus and added native FFmpeg render-throughput evidence (ED-0078).
- PRs #104-105 added review-agent tooling and model-effort routing.
- PR #103 added Session Assembly templates, frozen proposals, validation, and human approval (ED-0077).

## 2026-09-24

- PRs #96 and #99-100 accepted white-label program-source direction and implemented the provider-neutral source and presentation pass (ED-0079, ED-0080).
- PR #98 approved the Session Assembly foundation plan (ED-0077).
- PRs #94 and #97 planned and added Packaging Asset identity, content revisions, and human approval (ED-0076).
- PR #95 approved the native FFmpeg render benchmark plan (ED-0078).
- PR #93 excluded optional operator-installed transcription dependencies from distributable artifacts (ED-0075).
- PR #92 added the NVENC render benchmark harness and first recorded rendering evidence (ED-0073).

## 2026-08-28

- PR #91 refined the render benchmark corpus and quality measurement (ED-0073).
- PR #90 recorded Demo 2 promotion closure and reconciled plan status (ED-0074).
- PR #89 added append-only Editorial review, Editorial Clips, and the bounded review queue (ED-0072).
- PR #88 accepted Packaging Asset identity and policy-scoped automatic authority, and selected the transcription distribution boundary (ED-0075; Packaging Assets later implemented by ED-0076).
- PR #87 approved the Editorial review, render benchmark, and Demo 2 closure plans (ED-0072-0074).
- PR #86 accepted NVENC rendering and the GPU worker requirement, informing ED-0073.

## 2026-08-24

- PR #85 approved the Demo 2 hardware rehearsal plan (ED-0071).
- PR #82 added the Kernel-derived Producer Work Queue (ED-0068).
- PR #83 remediated frontend dependency security and lockfile integrity findings (ED-0069).
- PR #84 recorded hosted CI durability and frontend-test verification (ED-0056).

## 2026-08-23

- PR #81 reconciled repository implementation and merge status (ED-0070).
- PR #79 added the human-declared Editorial Candidate Moment foundation (ED-0067).
- PR #76 decomposed the media coordinator, documented the external integration boundary, and refreshed the dependency license SBOM (ED-0064-0066).
- PR #80 approved the frontend dependency security remediation plan (ED-0069).
- PR #78 approved the Kernel-derived Producer Work Queue plan (ED-0068).

## 2026-08-22

- PR #77 approved the human-declared Editorial Candidate Moment implementation plan (ED-0067).

## 2026-08-21

- PR #75 approved the coordinator safety-net, decomposition, integration ADR, and SBOM follow-ups (ED-0063-0066).
- PR #74 added shared-secret API protection, explicit CORS, CI durability/frontend tests, coverage reporting, failure logging, immutable response mappings, and documentation/tooling reconciliation (ED-0055-0062).
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
