# Real-Event Playback Validation Run 002

## Disposition

**PASS — Real-media Durable Event-Mode Kernel baseline**

Run 002 is accepted as the first successful real-media baseline for the Durable
Event-Mode Kernel. Against one disposable rehearsal Event, one Stage, and real
vMix-produced MP4 blocks, the bounded Kernel preserved 20 physical blocks as 20 durable
Candidates, registered 20 Completed Media Assets, associated all 20 deterministically
with the realized Session, preserved authoritative Presentation Start and Presentation
End, completed package review and human approval for package revision 1, and reconstructed
the same completed Session/package and media facts after fresh startup reconciliation.
No media was lost, unresolved, or conflicting.

This disposition validates the checked-out Kernel's real-media discovery, conservative
readiness, registration, association, Session/package authority, PostgreSQL durability,
and reconstruction behavior within the scope of this run. It is not production or Event
readiness, visual Producer or Editorial UX validation, or validation of post-Kernel AI,
worker, Candidate Moment, Assembly, automation, rendering, or delivery capabilities.

## Result identity and handling

- **Run ID:** `cba1efec-71ba-445c-a4d6-473d2670f125`
- **Run date:** 2026-08-10 through 2026-08-11 UTC
- **Mode:** vMix rolling replay at `1.0x`
- **Corpus item:** `reference-main-001`
- **Corpus manifest:** Not recorded in the external run record
- **Event mode / network policy:** `rehearsal` / `local_only`
- **Kernel configuration schema:** `1.0`
- **Stage/source scope:** one Stage, `main`; one configured source
- **Repository baseline:** working tree based on `74f23b4d60666032067c2710bf02eacccdf36c96`
- **External evidence:** retained outside Git; this result intentionally omits its private
  absolute path, DSN, media filenames, internal operation IDs, and corpus content
- **Media and corpus handling:** media remained outside Git and was not modified by this
  documentation closure

## Real-media and Session evidence

| Evidence | Result |
| --- | --- |
| Physical MP4 blocks | 20 |
| Durable Candidates | 20 |
| Registered Completed Media Assets | 20 |
| Deterministic Session associations | 20 |
| Stabilizing after final processing | 0 |
| Unresolved associations | 0 |
| Conflicting associations | 0 |
| Media loss | None observed |
| Final Session activity state | `presentation_ended` |
| Intermediate package review state | `ready_for_review` |
| Final package state | `complete` |
| Final package revision | 1 |
| Final Session revision | 4 |

The authoritative Presentation Start was persisted at
`2026-08-10T13:10:29.093106-07:00`. The authoritative Presentation End was persisted at
`2026-08-10T13:26:22.880605-07:00`. Session activity and package state remained separate:
the Session was already `presentation_ended` while trailing media continued to arrive,
stabilize, register, and associate while the package remained `assembling`.

The last MP4 modification-time proxy was
`2026-08-10T13:30:52.413151-07:00`; vMix recorded `StopRecording` at approximately
13:30:52 local. The final asset registered at
`2026-08-10T13:31:11.141541-07:00`, 288.261 seconds after authoritative Presentation End.
Filesystem modification time is a proxy for block close except where the recorder log
supplies the final stop evidence.

The explicit Package Ready command completed at
`2026-08-11T01:08:26.414700+00:00`, transitioning the package to `ready_for_review`.
The attributable human approval completed at
`2026-08-11T01:09:02.926206+00:00`, transitioning package revision 1 to `complete` and
advancing the Session to revision 4.

## Bounded-cycle evidence

- 313 completed bounded cycles were recorded.
- Cycles observed 2,571 Candidate appearances because each full cycle rediscovered the
  bounded current source contents; this is not 2,571 distinct Candidates.
- 20 assets registered and no source discovery failure was recorded.
- Cycle duration was 0.068845 seconds minimum, 3.066644 seconds average, and 7.853169
  seconds maximum.
- Seven transient inspection failures affected six still-growing Candidate identities.
  Every affected Candidate was later observed successfully and registered under the same
  durable identity.
- Empirical cycle cost increased approximately linearly with the number of files in the
  shallow source. This is evidence for later operational optimization, not an accepted
  correctness defect or violation of a defined runtime cadence SLA.

Run 002's normal approximately one-minute blocks took a median 59.962 seconds from
filesystem creation to final modification. Under continuous cycle execution, the normal
final-modification proxy to readiness interval was 6.940–18.728 seconds, with a median
of 10.519 seconds. Two longer intervals, 65.487 and 124.549 seconds, were caused by the
gap between live and trailing qualification commands rather than continued media writes.

## Package and reconstruction evidence

Package review and completion occurred only after authoritative Presentation End. A
fresh process reconstruction was then invoked against the preserved PostgreSQL and
source state.

Startup reconciliation:

- started at `2026-08-10T18:10:32.703479-07:00`;
- completed at `2026-08-10T18:10:39.074373-07:00`;
- observed 20 Candidates and created no duplicate asset registration;
- completed without a failure code;
- restored `ready = true` and `recovering = false`;
- exposed zero attention codes; and
- preserved 20 registered and 20 associated media with zero stabilizing, unresolved, or
  conflicting media.

The reconstructed repository preserved the completed Session/package facts, package
revision 1, Session revision 4, association history, and media identities. PostgreSQL
availability remained distinct from reconciled readiness.

## Qualification findings and dispositions

| Finding | Classification | Closure disposition |
| --- | --- | --- |
| Run 001 source path did not match the actual vMix output directory | Procedure/configuration issue | Corrected operationally for Run 002; the runbook requires exact source-path verification before playback. |
| Run 001 allowed Package Ready while Presentation was active | Application guard defect | Corrected at the authoritative application boundary. Package readiness and completion now require `presentation_ended` and a non-null authoritative end. |
| Run 002 emitted transient `OSError` results while vMix was growing files | Expected conservative inspection race plus observability issue | Candidate identity and evidence were preserved and retried; all media registered. The safe typed `candidate_replaced_during_observation` cycle outcome is now exposed for the existing guard. |
| Full bounded-cycle cost increased with Candidate count | Future operational optimization | Approximately O(N) per full cycle. No accepted correctness defect or two-second runtime SLA failure is claimed. No worker, watcher, scheduler, or queue design is selected here. |
| An interrupted cycle could leave a durable reconciliation at `running` until superseded | Future bounded recovery/status investigation | Explicit reconciliation and later startup reconciliation succeeded. Preserve for investigation without changing reconciliation semantics in this closure. |

## UX evidence

Run 002 supplies implementation-grounded evidence for later UX design, not proof that a
Producer or Editorial interface is implemented or validated:

- Presentation End and Media Assembly must remain visibly distinct.
- Session activity state and package state must remain separate.
- Default per-block and per-cycle Candidate activity would be too noisy under Event-day
  pressure.
- Producer views should prefer Stage/Session-level associated, stabilizing, unresolved,
  and conflicting counts, with media-level detail on demand.
- Expected growing-file inspection races should remain visually quiet while recovery is
  progressing; persistence or operational consequence, not the exception alone, should
  govern attention.
- Performance telemetry should remain separate from Producer Attention unless it causes
  a meaningful workflow consequence.

These observations reinforce the existing shared visual principle that healthy state is
quiet, consequence precedes technical telemetry, and operational detail is progressively
disclosed.

## Scenario evidence and limits

Run 002 contributes evidence to the normal-operation baseline in Scenario A of the
[Event-Day UX Scenario Validation specification](../../ux/event-day-scenario-validation.md),
scoped to one Stage and one realized Session. It does not validate the complete
multi-Stage scenario, same-Stage turnover, visual interaction behavior, Editorial work,
AI-derived Candidates, worker degradation, Assembly, or automation.

Environment details not captured in the external record—such as the exact OS build,
PostgreSQL version/deployment class, clock-synchronization measurement, corpus manifest
revision, and complete vMix repeatability settings—remain limitations. They do not alter
the bounded Kernel/media disposition, but later comparative runs should record them. The
run used a working tree with uncommitted corrections, so the recorded base commit alone
does not reproduce the exact validation tree; later baselines should retain an exact
committed revision or reviewed patch identity.

## Next experiment

The repository is ready to prepare the bounded same-Stage turnover experiment described
by the [real-event validation runbook](../../plans/real-event-playback-validation.md).
That experiment should use fresh disposable Event/Session authority and external media
and result records. Run 002 remains preserved as the one-Session baseline and must not be
repurposed or rewritten.
