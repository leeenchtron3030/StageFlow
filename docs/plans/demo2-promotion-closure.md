# Demo 2 promotion closure and plan-status reconciliation

## Status

Completed

## Execution authority

- Classification: Green autonomous for recording evidence and reconciling plan status.
  **Merging PR #71 is explicitly excluded and remains a separate human decision.**
- Authority evidence: the operator's 2026-08-28 report that the Demo 2 two-machine
  rehearsal completed on real machines and succeeded; ED-0071's
  [Demo 2 hardware rehearsal](demo2-hardware-rehearsal.md) plan, whose completion record
  is currently unfilled; PR #71's own stated promotion gate; the ED-0070
  [repository consistency closure](repository-consistency-closure.md) precedent, which
  established that plan/directive status drifting from reality is a recurring defect
  worth closing promptly.
- Implementation-ready: Yes for reconciliation, **conditional on the operator supplying
  the actual run evidence.** See the explicit dependency below.
- Required escalation or approval, if any: this plan must not merge PR #71, must not mark
  any ED-0071 acceptance criterion satisfied without corresponding evidence, and must not
  characterize the rehearsal beyond what the recorded evidence supports.

## Related findings or ADRs

- Finding: ED-0071's rehearsal has been executed but its evidence exists only in operator
  memory and outside the repository. The repository is supposed to be the durable source
  of truth; an executed-but-unrecorded rehearsal is exactly the drift ED-0070 closed.
- Finding: several plans remain `In progress` with completion conditions that may now be
  satisfied — `demo-hardware-rehearsal.md` (Demo 1, several unchecked criteria),
  `demo-rehearsal-controller.md`, `stable-ingress-identity.md` ("implementation complete;
  real PostgreSQL execution pending"), and `producer-ux-operational-refinement.md`.
- Engineering Directive: ED-0074. Closes ED-0071; follows the ED-0070 precedent.

## Problem statement

The Demo 2 rehearsal — PR #71's sole stated promotion gate — has been run successfully on
real hardware, but nothing in the repository records it. ED-0071's plan still shows an
unfilled completion record and ten unchecked acceptance criteria, `ENGINEERING_DIRECTIVES.md`
still shows ED-0063 as "live promotion gate pending," and PR #71's own body still states
Demo 2 "is not promotion-qualified." A future reader — human or agent — would draw exactly
the wrong conclusion about what StageFlow has proven.

## Verified current behavior

- `docs/plans/demo2-hardware-rehearsal.md`: Status `Approved`; all ten acceptance criteria
  unchecked; completion record reads "_(To be filled in by whoever executes this
  rehearsal.)_".
- `ENGINEERING_DIRECTIVES.md` ED-0063 row: "Implemented on draft PR; live promotion gate
  pending". ED-0071 row: "Approved".
- PR #71: open, draft, body states "Demo 2 is not promotion-qualified. The remaining gate
  is a fresh two-machine live rehearsal."
- No `docs/validation/results/demo2-hardware-rehearsal-*.md` exists.

## Explicit evidence dependency

**This plan cannot be completed from the operator's summary alone.** ED-0071 requires a
factual result "distinguishing passed, failed, unavailable, and unqualified facts," and
the repository's plan process requires a completion record naming commands run, observed
results, and deviations. Before reconciliation, the operator must supply, at minimum:

- which acceptance criteria were actually exercised, and the observed outcome of each;
- whether autonomous media progression, automatic CUDA transcription, Mac-UI Package
  Approval, the induced-failure safety-net check, and restart reconstruction each ran;
- any deviation from the planned procedure, and any blocker found and corrected;
- whether a real Devcon PUT occurred;
- bounded environment facts (versions, GPU, driver, block counts, timings) without
  secrets, media paths, or transcript content.

If a criterion was not exercised, it is recorded as **not qualified** — not as passed.
A criterion with no evidence must never be checked off.

## Desired behavior

The repository durably and truthfully records what the Demo 2 rehearsal did and did not
prove, ED-0071's plan and the directive index match that reality, and any other plan whose
completion conditions are genuinely satisfied is reconciled — while PR #71's merge remains
an open, explicitly human decision.

## In scope

- Create `docs/validation/results/demo2-hardware-rehearsal-001.md` from the operator's
  supplied evidence, using the existing
  [run-result template](../validation/real-event-playback-run-result-template.md)
  conventions and distinguishing passed / failed / unavailable / not-qualified.
- Update ED-0071's plan: Status, acceptance criteria checked **only where evidence
  supports it**, and a real completion record.
- Update the ED-0063 and ED-0071 rows in `ENGINEERING_DIRECTIVES.md` and their
  `docs/plans/README.md` index rows to match.
- Review the four `In progress` plans named above; reconcile only those whose completion
  conditions are demonstrably satisfied, and leave the rest with an accurate current
  status.
- Record explicitly whether Demo 2 is now promotion-qualified, as ED-0071's acceptance
  criteria require.

## Out of scope

- **Merging PR #71, or removing its draft status.** Even if the rehearsal qualifies Demo 2,
  the merge is a separate human decision; this plan records evidence and status only.
- Fabricating, inferring, or generously interpreting any evidence not supplied.
- Re-running any part of the rehearsal.
- Any production code, schema, migration, dependency, or runtime configuration change.
- Reopening the association-reevaluation Yellow extension or any other accepted decision.

## Constraints

- Truthfulness over tidiness: an unexercised criterion stays unchecked. A partial
  qualification is recorded as partial, following the Run 003/Run 004 precedent where
  invalid and partial runs were preserved honestly rather than rewritten.
- Privacy: no secrets, DSNs, credentials, media paths, or transcript content.
- Preservation: do not rewrite ED-0071's original plan text to make the outcome look
  cleaner; record deviations as deviations.

## Implementation approach

1. Collect the operator's rehearsal evidence (see the explicit dependency above).
2. Write the sanitized result document, marking each ED-0071 acceptance criterion
   passed / failed / unavailable / not qualified with its evidence.
3. Update ED-0071's plan status, criteria, and completion record to match the result.
4. Update the ED-0063 and ED-0071 directive rows and plan-index rows.
5. Review the four `In progress` plans; reconcile only the genuinely satisfied ones.
6. State the promotion-qualification conclusion explicitly, and leave PR #71 draft.

## Files or modules expected to change

| Path or module | Expected change |
| --- | --- |
| `docs/validation/results/demo2-hardware-rehearsal-001.md` | Sanitized factual result (new) |
| `docs/plans/demo2-hardware-rehearsal.md` | Status, evidence-backed criteria, completion record |
| `ENGINEERING_DIRECTIVES.md` | ED-0063 and ED-0071 row status |
| `docs/plans/README.md` | Matching index rows |
| Four `In progress` plans | Reconciled only where genuinely satisfied |
| `docs/validation/README.md` | Index the new result |

## Data or migration considerations

None. Documentation only.

## Failure and recovery considerations

If the supplied evidence is incomplete or ambiguous for a given criterion, record that
criterion as not qualified and name what is missing. Do not resolve ambiguity in the
project's favour.

## Observability requirements

Not applicable — documentation reconciliation only.

## Test strategy

- `git diff --check` and deliberate diff review.
- Relative-link validation for changed documents.
- Secret/privacy scan of the new result document.
- No code changes, so no test suite run is required beyond confirming none were made.

## Acceptance criteria

- [ ] A sanitized Demo 2 rehearsal result exists and distinguishes passed / failed /
  unavailable / not-qualified per ED-0071 criterion.
- [ ] Every checked ED-0071 acceptance criterion has corresponding recorded evidence; no
  criterion is checked without it.
- [ ] ED-0071's plan status and completion record match the result.
- [ ] ED-0063 and ED-0071 directive and plan-index rows match reality.
- [ ] The result states explicitly whether Demo 2 is promotion-qualified.
- [ ] The four `In progress` plans are reviewed; only genuinely satisfied ones are
  reconciled.
- [ ] PR #71 remains open and draft; no merge occurred.
- [ ] No secrets, media paths, or transcript content appear in any new document.

## Rollback or reversal

Documentation-only and directly revertible.

## Open questions

- Does the operator want the Demo 1 hardware rehearsal plan's remaining unchecked criteria
  closed in the same pass, or preserved as separately pending?

## Completion record

- **Evidence supplied:** the operator's 2026-08-26 final-state report plus explicit
  confirmation on 2026-08-28 that ED-0071 criteria 4, 6, and 7 were **not exercised**.
- **Recorded:** [Demo 2 hardware rehearsal Run 001](../validation/results/demo2-hardware-rehearsal-001.md)
  as a PARTIAL QUALIFICATION — seven criteria pass, three recorded NOT QUALIFIED rather
  than inferred or generously interpreted, per this plan's own constraint.
- **Reconciled:** ED-0071's plan status, acceptance criteria, and completion record; the
  ED-0063, ED-0071, and ED-0074 directive rows; and the matching plan-index rows.
- **Drift found and corrected in the `In progress` review:** `demo-rehearsal-controller.md`
  and `producer-ux-operational-refinement.md` both declared themselves Completed/Complete
  in their own Status blocks while the plan index still listed them as In progress. Index
  corrected to match. `demo-hardware-rehearsal.md` (Demo 1) and `stable-ingress-identity.md`
  were reviewed and are genuinely still in progress; both left unchanged.
- **Promotion state:** Demo 2 is **not promotion-qualified**. PR #71 verified open and
  draft on 2026-08-28 and deliberately not merged.
- **Commands run:** `gh pr view 71` for draft-state verification; `git diff --check`;
  deliberate diff review. No code changed, so no test suite was run.
- **Execution authority used:** Green autonomous documentation reconciliation.
- **Approved deviations:** none.
- **Rollback status:** documentation-only and directly revertible.
- **Remaining work:** a follow-up rehearsal exercising only criteria 4, 6, and 7.
