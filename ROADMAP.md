# StageFlow roadmap

This roadmap lists only accepted or already-tracked work. It is not a production-readiness
claim and does not supersede ADRs, Engineering Directives, or implementation plans.

## Current closure

- Complete and validate ED-0055 through ED-0062 due-diligence remediation.
- Observe the first real GitHub Actions run with PostgreSQL durability tests, frontend
  tests, and backend coverage output.
- Have the repository owner require `Backend / Python 3.13` and `Frontend / Node 22` in
  branch protection.

## Next operational gate

- Complete the tracked Demo hardware rehearsal prerequisites and execute the Demo 2 live
  rehearsal gate with the accepted controller and qualification procedures.
- Record hardware, PostgreSQL restart/replay, transcription, timing-evidence, and operator
  workflow evidence without treating partial qualification as event readiness.

## Later accepted work

- Continue the post-Kernel capability layer only through bounded plans and accepted ADRs.
- Revisit broader transcription/provider selection when the existing conditional criteria
  are met.

## Open owner decision

- Decide whether fresh independent code review becomes a mandatory repository-wide gate.
