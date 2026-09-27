# Derived Editorial candidates from transcript phrase matches

## Status

Completed (2026-09-26).

## Execution authority

- Classification: Green autonomous.
- Authority evidence:
  - The owner approved the default on 2026-09-25 (Yellow decision "machine-origin, derived
    Editorial candidates"):
    - the first rule is an operator-supplied, versioned phrase list, matched
      deterministically against Transcription Evidence revisions;
    - the results are advisory candidates only;
    - human review is unchanged.
  - On 2026-09-26 the owner decided that media timing comes first. It now exists (ED-0090)
    and is consumed by Assembly (ED-0091).
  - [ADR-0033](../adr/ADR-0033-production-media-timing-inspection.md) decision 5 names
    derived Editorial placement as a permitted advisory consumer of MTE. It must record the
    evidence revision and qualification it used.
  - The Editorial Phase 1 plan reserved the four-origin vocabulary (`observed` / `derived` /
    `inferred` / `declared`) for this, and left machine-origin candidates Yellow-gated until
    the owner approved them.
  - The Product Constitution, principle 5: "AI assists. Humans publish." AGENTS.md says to
    use direct synchronous calls for deterministic domain decisions.
- Implementation-ready: Yes.
- Required escalation: stop if this would:
  - let a derived candidate be approved, clipped, or published without the existing human
    review;
  - generate candidates automatically without a human command;
  - use a model or network provider;
  - write transcript evidence, MTE, Session, association, or package state;
  - change the review, clip, or declared-candidate semantics;
  - alter an existing constraint's meaning for declared rows.
- Engineering Directive: **ED-0092**. The owner delegated ED numbering.

## Preserved accepted decisions

- **Editorial Phase 1 (ED-0070/0071):**
  - Human-declared candidates keep exactly their current contract, reason code
    (`human_mark_moment`), source kind, idempotent command, and location semantics.
  - The four-origin vocabulary is unchanged. `derived` becomes usable only for the new
    source kind.
- **Editorial review (ED-0072):**
  - The review actions (approve and create clip, reject, revise range, defer), their
    human-only authority, the derived review state, and clip creation are unchanged.
  - Derived candidates enter the same review queue and are reviewed the same way.
- **ADR-0027 / ADR-0033:** MTE and transcript evidence stay advisory inputs. This plan only
  reads them, and records exactly which revisions it used.
- **Session location semantics:** a candidate is located on the Session timeline, in
  microseconds from the Session's authoritative start, and location conflicts against
  Session boundaries are evaluated exactly as they are for declared candidates.

If an existing assertion would have to change, stop and report it. Pre-authorized
exceptions:
- inserting `0019` into the migration-order lists;
- mechanical constructor or field additions that keep existing values;
- setup-only baseline adjustments that keep an assertion's meaning.

## Problem statement

Producers mark every moment by hand. Transcripts already exist for recorded media, and
since ED-0090 each file has an advisory start time. StageFlow can now propose moments where
an operator-chosen phrase is spoken, and place them on the Session timeline for human
review.

## Verified current behavior

- `0008` `editorial_candidate_moment`:
  - `origin = 'declared'`, `epistemic_kind = 'declared'`,
    `reason_code = 'human_mark_moment'`, and `revision = 1`;
  - `operation_id` is required, unique, and references `human_command_idempotency`;
  - locations are Session-timeline microseconds, with the Session's authoritative
    start/end snapshot;
  - `0010` adds location-history rows.
- `backend/app/contexts/editorial/contracts.py`:
  - `EditorialCandidateMoment.__post_init__` rejects any origin other than `declared`, and
    any source kind other than `producer_declaration`;
  - `EditorialCandidateOrigin` already lists four values;
  - `EditorialCandidateSourceKind` has one value.
- `0007` transcript evidence:
  - `transcript_evidence_revision` has an asset, revision, and status;
  - `transcript_evidence_segment` and `transcript_evidence_word` hold text and asset-relative
    microsecond ranges, with ordinals.
- ED-0090 MTE: the latest active revision per asset, with one Derived
  `creation_time_plus_duration` interval and a qualification status.

## Design decisions (bounded and deterministic)

1. **Phrase list** is a new Event-scoped, immutable, versioned aggregate:
   - key, version, name, 1–200 phrases, created by and at;
   - each phrase is 1–100 characters after trimming;
   - normalization: Unicode NFKC, then casefold, then collapse whitespace;
   - tokenization: split into alphanumeric word tokens (Unicode-aware);
   - duplicate phrases are rejected after normalization;
   - it is published by an idempotent human command; a new version never mutates an old one.
2. **The derivation run** is a human-invoked, synchronous, idempotent command:
   `derive_candidates(session_id, phrase_list_id, version, actor, command_id)`.
   - **Inputs:** the Session's currently associated assets (Kernel association). For each
     asset, the latest `complete` transcript evidence revision, and the latest active MTE
     revision with exactly one `creation_time_plus_duration` Derivation.
   - **Run identity:** Session, phrase-list version, and the sorted (asset, transcript
     evidence ID, MTE evidence ID and revision) input set. Replaying the same inputs returns
     the existing run. A changed input set creates a new run.
   - **Bounds:** at most 500 candidates per run.
   - **Skip counts:** reported per reason: `no_transcript`, `no_timing_evidence`,
     `no_session_start`, `outside_session`, and `limit_reached`.
3. **Matching.** A phrase matches a contiguous sequence of word tokens within one
   transcript segment, with word text normalized as above and tokens compared exactly.
   - Every occurrence counts.
   - Overlapping matches of the same phrase in one segment keep the earliest start.
   - Matches of different phrases are separate candidates.
4. **Placement.** A match's start is:

   `MTE candidate_started_at + first word asset_start − Session authoritative_start`

   Its end is computed the same way from the last word's `asset_end`. Both are in
   microseconds.
   - A match that starts before the Session start is skipped (`outside_session`).
   - Location conflicts against the Session end are evaluated exactly as for declared
     candidates, recording `partially_excluded` or `excluded`.
5. **A derived candidate** uses the existing aggregate and table:
   - `origin = epistemic_kind = 'derived'`;
   - `source_kind = 'transcript_phrase_match'`;
   - `reason_code = 'transcript_phrase_match'`;
   - `revision = 1`;
   - no `operation_id` (a derived candidate is not a human command). It references its run
     instead.

   A new provenance row, one per candidate, holds:
   - the run, phrase-list ID and version, and the normalized matched phrase;
   - the asset, the transcript evidence ID and revision, the segment ID, and the first and
     last word IDs;
   - the asset-relative start and end;
   - the MTE evidence ID and revision, and its qualification.
6. **Review.** Derived candidates appear in the existing queue and projections with their
   origin, a provenance summary (phrase, timing qualification), and the unchanged review
   actions. Nothing is approved, clipped, or published automatically.

## In scope

1. Contracts (Editorial context):
   - the phrase list;
   - the derivation run and its result, including skip counts;
   - `EditorialCandidateSourceKind.TRANSCRIPT_PHRASE_MATCH`;
   - validation of the derived candidate and its provenance, with each source kind's rules
     enforced separately. Declared validation is unchanged.
   - Pure matching and placement functions.
2. Reader ports in the Editorial context for the Session's associated assets, the latest
   complete transcript evidence (segments and words), and the latest active MTE Derivation.
   There are in-memory and PostgreSQL implementations, with bounded queries.
3. Service commands: `publish_phrase_list` and `derive_candidates`. Both are human-only
   and idempotent, and they run in one transaction per run.
4. Migration `0019`:
   - `editorial_phrase_list` and `editorial_derivation_run`, append-only with immutability
     triggers;
   - `editorial_candidate_provenance`, with a primary key and foreign key on the candidate,
     and foreign keys to the run, transcript evidence, and MTE (composite
     `(asset_id, evidence_id)` where available);
   - make the `editorial_candidate_moment` checks kind-aware:
     - `declared` rows keep exactly the current `origin`, `epistemic_kind`, `reason_code`,
       and `operation_id` requirements;
     - `derived` rows require `reason_code = 'transcript_phrase_match'`, a NULL
       `operation_id`, and a provenance row;
     - no existing constraint's meaning changes for `declared` rows.

   The reverse is refused while any derived candidate, run, or phrase list exists. It is
   registered after `0018` by plain chaining.
5. API, authenticated and bounded:
   - `POST` to publish a phrase list, and `GET` its versions;
   - `POST` to derive candidates for a Session, returning the run, candidate IDs, and skip
     counts;
   - the existing candidate and queue reads additively expose origin and provenance.

   No paths.
6. Tests, behaviour-first, in memory and real PostgreSQL:
   - phrase-list normalization and bounds;
   - matching: multi-word, case and Unicode, overlaps, segment boundary, several phrases;
   - placement arithmetic, including the Session start and end conflicts;
   - skip reasons;
   - run idempotency, and a new run when the inputs change;
   - the 500-candidate bound;
   - derived candidates flowing through the unchanged review actions and clip creation;
   - declared behaviour unchanged, including the exact existing assertions;
   - `0019` forward, reverse, and reapply, the refused reverse, and negative inserts for
     each check;
   - API authentication, bounds, and no paths.
7. Documentation: glossary (phrase list, derivation run, derived candidate), persistence
   (`0019`), the capability layer's Editorial section, and the MTE and transcript
   architecture documents (new consumer).
8. **Owner step.**
   - Publish a small phrase list for the live-run Event.
   - Derive candidates for the live-run Session. Its media has transcript evidence from
     the Demo 2 live run; use the current evidence and record the counts.
   - Check that the candidate placements match the word times plus the MTE start.
   - Record a sanitized validation result, with no transcript content: counts and
     placements only.

## Out of scope

- Automatic derivation triggered by new transcripts, model or AI inference, `observed` or
  `inferred` origins, and fuzzy matching.
- Frontend UI.
- Changes to review, clip, or declared-candidate semantics.

## Constraints

- No dependency. Offline. Timezone-aware times. Immutable contracts. White-label naming.
- No transcript text in logs, test fixtures from real events, or documentation.
  Phrase lists are operator data.

## Data or migration considerations

`0019` adds tables and changes the `editorial_candidate_moment` checks additively
(declared meaning preserved). There is no backfill. The reverse is conditional on no
derived rows.

## Acceptance criteria

- [ ] Phrase lists and derivation runs are implemented with deterministic matching and
  placement, idempotency, bounds, and skip reporting.
- [ ] Derived candidates carry full provenance and flow through the unchanged human
  review. Declared behaviour is unchanged.
- [ ] `0019` passes its forward, reverse, and reapply tests, including the refused reverse.
- [ ] The full host backend suite, Ruff, and Pyright pass, and the frontend is unchanged.
- [ ] The owner's run on the live-run Session records sane counts and placements.

## Rollback

Revert the code and apply the `0019` reverse (only while no derived rows exist).

## Completion record

- **Implemented revision:** branch `codex/ed-0092-derived-editorial-candidates`, stacked
  on ED-0091. Codex implemented it in one run with no escalation, and the owner committed
  it.
- **Files changed:**
  - Editorial derivation contracts, pure matching and placement, reader ports, the
    in-memory repository, and the service;
  - the PostgreSQL derivation repository;
  - migration `0019` (phrase lists, runs, command receipts, and provenance, with
    kind-aware candidate checks) and its registration;
  - the startup schema gate for `0019`, which follows the ED-0086 precedent because the
    candidate reads now join provenance;
  - the Editorial API;
  - tests;
  - the glossary, persistence, capability-layer, MTE, transcript-readiness, and Editorial
    README documents.
- **Review:** the `directive-reviewer` returned FIX-FIRST for test gaps. Codex fixed them,
  together with one owner-directed correction:
  - PostgreSQL and domain guards for declared rows;
  - persisted Session-end conflicts;
  - phrase identity by normalized token sequence, with punctuation-only phrases rejected
    (the owner's correction);
  - literal checks that the `0019` reverse restores the `0008` constraints.
- **Existing assertions changed:** only the pre-authorized `0019` additions to the
  migration-order lists.
- **Tests:** host full suite **2,562 passed, 0 failed, 2 skipped**; Ruff and Pyright
  are clean.
- **Owner host run:** see
  [Run 001](../validation/results/derived-editorial-candidates-001.md).
  - 30 derived candidates on the live-run Session, with 0 placement mismatches against an
    independent recomputation.
  - 1 boundary exclusion recorded.
  - Replay is idempotent, and nothing was reviewed automatically.
- **Deviations:** none from the design decisions.
- **Remaining work:**
  - The frontend `DemoMoment` type still assumes `origin: "declared"` and a non-null
    `operation_id`. Nothing reads them yet; a type update is needed before a UI shows
    derived candidates.
  - Run identity does not include the Session revision (per the plan), so after a
    boundary correction a new run needs changed inputs or a new phrase-list version.
  - A Producer UI for phrase lists and derived-candidate review.
