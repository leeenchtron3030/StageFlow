# StageFlow Editorial Temporal Workspace UX Specification
**Status:** Draft v0.1
**Source fidelity:** Exact chat draft.

> **Repository interpretation:** This exact Draft v0.1 records UX/product direction.
> No Editorial Temporal Workspace, candidate-review persistence, transcript runtime,
> playback integration, or Editorial frontend is implemented.

## 1. Primary Editorial Question

**What happened in this Session that is worth turning into content?**

Secondary questions include what is happening now, what StageFlow identified, what Producer marked, what was said, surrounding context, why suggested, whether useful, final range, review status, overlap, and downstream readiness.

## 2. Editorial Is Session-Centered

Editorial starts from the Session, not files, folders, worker jobs, transcript documents, model outputs, or media candidates.

## 3. Temporal Workspace Principle

Media, transcript, Candidate Moments, Producer marks, topics, observations, and Editorial decisions share one logical Session timeline.

## 4. Session Time vs Wall Clock

Editorial defaults to Session-relative time; wall clock remains secondary context.

## 5. Primary Layout

Core regions:

- Session Header
- Media Preview
- Master Session Timeline
- Transcript / Context
- Candidate Review Inspector
- Candidate Queue / Navigator
- optional topic/context tracks

## 6. Primary Workspace Regions

The exact geometry can change with display size but these functional regions remain stable.

## 7. Session Header

Show title, participants, organization/affiliation where known, Stage, package state/revision, duration, intelligence state.

## 8. Working Before Session Completion

Editorial may work during a live Session. Show live package and intelligence lag clearly. Preserve durable Session-relative context through later package correction.

## 9. Editorial Readiness

Possible states:

- Live
- Processing
- Ready
- Package Changed
- Intelligence Deferred

These are Editorial workflow states, not Session authority states.

## 10. Media Preview

Playback capabilities should support editorial judgment:

- play/pause
- seek
- current Session time
- skip backward/forward
- playback speed
- jump to Candidate
- loop Candidate range

## 11. Master Timeline

Potential tracks:

- media continuity
- transcript density
- Candidate Moments
- Producer marks
- Editorial decisions
- topics
- speaker changes later
- Session boundaries

Prioritize media, Candidate Moments, Producer marks, Editorial decisions.

## 12. Candidate Marker Semantics

Machine-generated, Producer-marked, approved, rejected should be distinguishable by icon + text, not color alone.

## 13. Candidate Moment

A Candidate means StageFlow or a human believes a time range deserves editorial review. It does not mean approved, factually correct, Marketing suitable, or publishable.

## 14. Candidate Range

Support point marker, approximate range, or precise in/out.

Editorial can adjust it without changing Session boundaries.

## 15. Candidate Origins

Support provenance from Producer mark, deterministic signal, AI/model inference, combined evidence.

## 16. Candidate Confidence

Avoid presenting raw model probability as editorial truth.

Prefer interpretable `Strong candidate` with provenance.

## 17. Producer Marks

High visibility; human declared; Editorial may approve/reject/adjust/defer.

Producer signal is strong evidence, not Editorial authority.

## 18. Manual Editorial Candidate

Editorial can mark a moment/create candidate even when StageFlow did not suggest it.

## 19. Candidate Review Inspector

Show range, duration, speaker/context, rationale, evidence, transcript preview, playback, approve/reject/defer.

## 20. Review Actions

Initial actions:

- Approve
- Reject
- Defer
- Adjust Range
- Add Note

Preserve append-only review history.

## 21. Approval Semantics

Approval means the Session range is worth preserving as downstream Editorial content. It does not imply rendered/branded/published.

## 22. Reject Semantics

Reject does not delete. Optional reasons may support later evaluation; reasons should not necessarily be mandatory during fast triage.

## 23. Defer Semantics

Defer means intentionally unresolved Editorial judgment, distinct from technical processing.

## 24. Candidate Range Adjustment

Support simple in/out controls without becoming a full NLE.

## 25. Context Playback

Provide `Play with Context` so Editorial can judge self-containedness without losing Candidate position.

## 26. Transcript Synchronization

Transcript follows playback; click transcript seeks video; selected transcript range can create/set Candidate.

## 27. Transcript Confidence and Corrections

Transcript is supporting intelligence, not authoritative truth. Weak transcript should not block media review.

## 28. Speaker Context

Support known, unknown, and multiple participants. Do not hide Candidate because diarization is uncertain.

## 29. Topic Context

Topics may help browse/group later but remain supporting metadata.

## 30. Live Editorial Mode

Show elapsed Session, transcript lag, Moment lag, Candidates, unreviewed.

Editor can review behind live; UI does not jump to newest Candidate.

## 31. Live Edge

Provide return-to-live control. Being behind live is normal.

## 32. Candidate Queue

Group by unreviewed/approved/rejected/deferred; prioritize Producer marks.

## 33. Candidate Sorting

Useful sorts:

- Session time
- suggested strength
- Producer-marked first
- unreviewed first

Maintain ordering stability while actively reviewing.

## 34. Candidate Deduplication

Presentation layer may group several signals around the same Moment without requiring durable merge semantics.

## 35. Nearby Candidates

Show related temporal Candidates/clusters.

## 36. Approved Editorial Clip Transition

Approval creates/enables canonical Editorial Clip downstream object; original Candidate remains historical.

## 37. Candidate-to-Clip Provenance

Preserve originating Candidate(s), reviewer, approved range, original range, package revision basis, evidence, review time.

## 38. Session Package Revision Change

Preserve Editorial work and report impact. Distinguish unaffected, source changed, outside boundary, missing media.

## 39. Boundary Change Affecting Candidate

Do not silently discard Candidate that falls outside corrected Session boundary.

## 40. Assembly Independence

Editorial works in Session-relative time. Assembly timing is derived separately.

## 41. Session Assembly Preview

Assembly context may be shown, but Editorial Moment review does not require Assembly approval.

## 42. Editorial Review Queue Across Sessions

Provide Event-level Editorial queue distinct from Producer Work Queue.

## 43. Editorial Priority

Potential priority: Producer-marked, explicit Hot/priority later, strong multi-signal, live, ordinary, deferred.

Model score alone does not determine publishing importance.

## 44. Editorial Work Modes

One application supports Live Triage and Deep Review.

## 45. Live Triage Layout

Prioritize video, Candidate queue, transcript, inspector, lag, actions.

## 46. Deep Review Layout

Give more room to timeline, transcript, clustering, topics, revision history.

## 47. Review Progress

Show Candidate totals and review progress.

## 48. Editorial Completion

Reserve concept `Editorial Review Complete` as separate future authority.

## 49. Worker Failure

New intelligence may be delayed; media and existing decisions remain usable.

## 50. Partial Intelligence

Separate transcript lag from Moment detection lag.

## 51. Offline / Event Mode Policy

Expected cloud deferral should not look like failure.

## 52. Human Review History

Show provenance/history of Producer mark, machine evidence, Editorial adjustments, approval.

## 53. Multi-Editor Concurrency

Refresh on concurrent update; prevent stale overwrite.

## 54. Keyboard-First Editorial Workflow

Keyboard speed matters; exact shortcuts should be validated before locking.

## 55. Speed of Review

Obvious Candidate review should take seconds and not require metadata forms.

## 56. Candidate Notes

Optional human notes support collaboration.

## 57. Sensitive / Do-Not-Use Flag

Reserve concept but do not invent semantics prematurely.

## 58. Participant / Organization Context

Show readily when available; optional metadata errors should not block review.

## 59. Marketing Boundary

Marketing consumes approved Editorial Clips, not raw Candidate stream.

## 60. Editorial Success Test

An editor joining 25 minutes into a Session should quickly understand Session identity, intelligence lag, Candidate counts, Producer marks, unreviewed work; an individual Candidate should be understandable in context within roughly 15 seconds.

## 61. Explicit Non-Goals

Not full NLE, compositor, render controller, publishing UI, social generator, distribution portal, schedule manager.

## 62. Product Principle

StageFlow watches continuously; Editorial judges selectively.

---
