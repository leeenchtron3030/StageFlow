# StageFlow Session Assembly & Approval Automation UX Specification
**Status:** Draft v0.1
**Source fidelity:** Exact chat draft.

> **Repository interpretation:** This exact Draft v0.1 records UX/product direction.
> Session Assembly, Packaging Asset identity, rendering, and policy-scoped automatic
> authority are not implemented. Their existing Yellow gates remain unchanged.

## 1. Core Distinction

StageFlow must distinguish:

### Session

The authoritative representation of what actually occurred on stage.

Includes:

- realized Session identity,
- actual Stage,
- authoritative presentation start,
- authoritative presentation end,
- associated recording media,
- package completeness history.

### Session Assembly

The presentation-ready arrangement built around the Session.

May include:

- opening branding,
- title graphics,
- bumpers,
- lower-thirds where later supported,
- Session media,
- closing branding,
- sponsor graphics,
- end cards,
- slates,
- other approved packaging media.

Branding assets do not alter the authoritative Session start/end.

## 2. Assembly Model

Conceptually:

Opening Asset(s)

→ Authoritative Session Content

→ Closing Asset(s)

The assembled duration may be longer than the authoritative Session duration. The UX must show those durations separately.

## 3. Assembly Templates

Support reusable Event-level or Stage-level Assembly Templates.

Templates may vary by:

- Event,
- Stage,
- Session type,
- sponsor category,
- track,
- distribution destination.

The Producer should not manually attach the same assets to every Session when an accepted template already defines them.

## 4. Branding Asset Library

Approved packaging assets should be available through an Event-scoped library.

Useful metadata:

- human-readable name
- role
- version
- duration
- Event applicability
- Stage applicability
- validity/effective dates where useful
- approval status

Raw filesystem location should not be the primary Producer-facing identity.

## 5. Automatic Assembly Suggestion

Once a Session package is sufficiently known, StageFlow should propose the expected Assembly automatically.

If everything matches a trusted template, little or no manual configuration should be required.

## 6. Assembly Timeline

Distinguish Assembly boundaries from Session boundaries.

Example concept:

`[ BUMPER ][ TITLE ][ SESSION ][ OUTRO ][ END CARD ]`

with authoritative Session START and END inside the Assembly.

## 7. Proposed Placement

StageFlow should suggest where packaging assets belong.

Placement may be deterministic from policy/template and provenance should say so, e.g.:

`DERIVED — Main Stage Assembly Policy v3`

## 8. Metadata-Driven Graphics

Graphics may populate from Session metadata such as:

- Session title
- participant(s)
- organization/affiliation

Panels must be supported.

Missing optional organization should not block Assembly unless the selected graphics template requires it.

## 9. Asset Validation

Before recommending or automatically approving an Assembly, validate applicable deterministic conditions:

- asset exists,
- expected version available,
- duration valid,
- media readable,
- template references resolve,
- required Session metadata exists,
- output timing coherent,
- Session package eligible,
- no unresolved material media,
- no conflicting asset ownership.

Do not silently omit unavailable required branding.

## 10. Missing Branding Asset

A missing expected asset should create Assembly review without invalidating the Session itself.

## 11. Session Completion vs Assembly Approval

Preserve separate states:

- Session Package Complete
- Assembly Proposed
- Assembly Approved
- Rendered / Delivered later

Changing an outro does not reopen Session completeness unless Session media itself changed.

## 12. Progressive Approval Modes

### Mode 1 — Manual Approval
Every consequential package/Assembly decision requires explicit human approval.

### Mode 2 — Assisted Approval
StageFlow automatically prepares deterministic work but stops for human approval.

### Mode 3 — Exception-Only Approval
StageFlow automatically approves cases satisfying explicitly trusted policy and escalates ambiguity, contradiction, missing evidence, untrusted configuration, unexpected media, boundary disagreement, unresolved association, continuity warning, missing branding, template mismatch, or other policy-defined exceptions.

### Mode 4 — Highly Automated Event Operation
Routine decisions may be substantially automated where explicitly authorized; humans work primarily by exception.

This mode must be explicitly enabled.

## 13. Automation Policy, Not Just Confidence

Automatic approval must not mean `AI confidence > threshold`.

Approval depends on explicit policy combining evidence and invariants.

Potential checks:

- accepted boundary evidence
- no competing candidate
- all relevant assets registered
- no unresolved ownership
- no conflicts
- no blocking continuity issue
- trusted Assembly Template
- expected asset versions
- metadata requirements satisfied
- authoritative database healthy
- reconciliation current
- provenance available

## 14. Confidence and Doubt

Represent doubt explicitly:

- Ambiguous
- Contradictory
- Insufficient Evidence
- Novel
- Out of Policy

These route work to humans.

## 15. Human Override

Auto-approved results remain inspectable and correctable. Corrections create new authoritative history/revisions. Prior automatic decisions remain historically recorded.

## 16. Automated Decision Provenance

Preserve:

- policy identity/version
- timestamp
- evidence used
- relevant model/version
- deterministic checks
- system state required by policy
- reason no human review was required

## 17. Trust Should Be Configured Explicitly

StageFlow may report historical automation performance but must not silently increase its own authority.

Historical performance provides evidence for trust; it does not grant authority.

## 18. Per-Decision Automation

Configure independently for decision types such as:

- Session start
- Session end
- media association
- package completion
- Assembly approval
- rendering
- publishing

Avoid one global Automation Boolean.

## 19. Event-Level Automation Profile

An Event may select an approved automation profile summarizing the mode per decision family.

## 20. Mission Control Representation

Mission Control should show automation outcomes without noise.

Routine automatic success: no intervention required.

If automation withholds approval, explain why and route to the relevant review workflow.

## 21. Stage Detail Representation

Expose current automation policy secondarily where useful.

## 22. Session Package Review Representation

Explain why human review is required, including which checks passed and which condition blocks auto-approval.

## 23. Auto-Approved Package View

Show policy, result, Session/package summary, Assembly, and review details without turning success into an alert.

## 24. Hot Moments and Assembly

Moment Candidates remain independent of package approval.

Their canonical timing remains Session-relative.

Adding opening branding must not shift logical Moment timestamps. Derived Assembly-output timestamps may be calculated separately.

## 25. Editorial Handoff

Editorial receives:

- authoritative Session
- approved/current package revision
- current Assembly definition where useful
- Moment Candidates
- Producer marks
- transcript/intelligence
- participant/organization metadata

## 26. Rendering

Rendering is downstream from Assembly approval.

Worker failure should defer rendering rather than invalidate the underlying Session package.

## 27. Assembly Revision

Changing packaging media creates an Assembly revision, not a Session package revision.

## 28. Package + Assembly Status

A Session may simultaneously show:

- Session Package Complete — revision 2
- Assembly Review Required — revision 4
- Render Not Started

Do not collapse downstream lifecycle into one Session status.

## 29. Success Condition

A mature deployment should allow most routine Sessions to be:

- identified/proposed,
- media associated,
- package verified,
- branding assembled,
- routine result approved under trusted policy,
- Moment Candidates generated,
- downstream processing initiated

with the Producer seeing primarily:

**No intervention required**

and occasional explicit human review where doubt remains.

## 30. Safety Principle

Automation authority increases through deliberate policy configuration and validated evidence.

When certainty is insufficient: defer to human.

When required dependency unavailable: fail closed for authoritative decisions.

When media ownership ambiguous: preserve and request review.

When trusted policy is satisfied: proceed without unnecessary human interruption.

---
