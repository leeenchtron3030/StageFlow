# Real-Event Playback Validation Run 003

## Disposition

**INVALID — intended same-Stage turnover qualification not executed**

Secondary finding: **PASS — media-without-Session-authority
preservation/conservatism diagnostic**.

Run 003 cannot establish same-Stage turnover behavior because its two Program
Expectations were recorded but neither expected Session was realized. Media ingestion
therefore occurred without Session authority. This document preserves the observed
qualification facts without repairing, replaying, or reinterpreting the external Run
003 artifacts.

## Sanitized observed evidence

| Evidence | Observed result |
| --- | --- |
| Program Expectations | A and B created |
| Realized Sessions | 0 |
| Physical MP4 blocks | 35 |
| Durable Candidates | 35 |
| Registered Completed Media Assets | 35 |
| Session associations | 0 |
| Unresolved associations | 35 |
| Conflicts | 0 |
| Conservative reason | `no_safely_eligible_session` |
| Trailing bounded cycles | 60 eventually completed |

The result is consistent with accepted authority semantics: a Program Expectation does
not realize a Session, and the Kernel did not invent Session authority or assign media
when no safely eligible Session existed. That conservatism is the bounded secondary pass;
it is not turnover evidence.

## Qualification-tooling incident evidence

- The Codex execution-host wait timed out while the long-running child continued.
- The timeout did not terminate that child.
- Reconciliation and checkpoint operations were launched while the child still ran.
- The late `DriveCycles` whole-document save overwrote newer external run-record command
  entries from those operations.
- PostgreSQL reconciliation evidence preserved the actual operations even though the
  external run record lost their later command entries.

These were qualification-controller and external-evidence hazards, not a basis for a
production Kernel, persistence, scheduler, worker, or distributed-lock decision. The
bounded correction is recorded in the
[Run 004 qualification-tooling hardening plan](../../plans/run-004-qualification-tooling-hardening.md).

## Preservation and limits

Run 003's database, media, external JSON/Markdown record, environment metadata, and
other evidence remain outside Git and were not modified while creating this sanitized
result. This document omits credentials, private absolute paths, filenames, operation
identities, and sensitive corpus content. Run 003 must not be called a turnover success
or reused as Run 004.
