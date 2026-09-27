# Derived Editorial candidates - Host validation Run 001

## Status and authority boundary

**PASSED - On the live-run Session, a human-invoked derivation run turned phrase matches in
real Transcription Evidence into `derived` Editorial candidates.**

- Every placement matched an independent recomputation exactly.
- Session-boundary conflicts were recorded correctly.
- Nothing was reviewed, approved, or clipped automatically.

This is the owner's host step for ED-0092 (plan in-scope item 8). It is **not** a claim
about the editorial usefulness of phrase matching, and it is not evidence of Event
readiness.

No transcript text, phrase text, media path, filename, username, or connection string is
recorded here. Phrases are identified only as P1–P3.

## Setup

- **Database:** the local demo database, backed up with `pg_dump` first, then migrated
  forward to `0019`.
- **Code:** branch `codex/ed-0092-derived-editorial-candidates`.
- **Session:** the 2026-08-26 live-run Session. It has 11 associated assets, each with one
  `complete` Transcription Evidence revision (1,546 word tokens in total) and one
  `unqualified` MTE revision from ED-0090.
- **Commands:** phrase lists were published and runs derived through
  `EditorialDerivationService`, with human authority and persisted command IDs.

## Results

| Check | Result |
| --- | --- |
| Phrase list v1: five generic phrases chosen without looking at the transcript | run succeeded with 11 inputs, **0 candidates**, and every skip count 0. None of the phrases occurs in the transcript. |
| Replay of the v1 command | returned the same run; no new rows |
| Phrase list v2: three single-word phrases chosen from frequent vocabulary | run succeeded with 11 inputs and **30 candidates** (P1: 15, P2: 9, P3: 6). Every skip count 0. |
| Candidate identity | all `derived`, reason `transcript_phrase_match`, no command operation ID, provenance row present |
| Timing qualification in provenance | `unqualified` on all 30 |
| **Placement** | an independent SQL recomputation of MTE `candidate_started_at` − Session authoritative start + the first word's asset start (end: + the last word's asset end) gave **0 mismatches across 30 candidates** |
| Timeline span | 151.559 s to 669.779 s after the Session start (Session length 665.192 s) |
| Session-boundary conflicts | 1 candidate lies beyond the Session end and is recorded as `excluded_by_session_boundary`; 29 have no conflict |
| Review | 0 review decisions exist for derived candidates. All of them await human review. |

## Interpretation

The capture → transcription → media timing → derived-candidate chain works end to end on
real rehearsal media:
- Placement is exact, given the advisory, unqualified timing evidence.
- Idempotency and boundary handling work as the plan specifies.

Limits:
- The candidates' editorial value depends entirely on the operator's phrase choice. This
  run validates the mechanism, not the choice.
- The placement accuracy against real speech inherits the unqualified semantics of the
  recorder's `creation_time`.
- A single Session was tested.
