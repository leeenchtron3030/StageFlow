# Producer and Editorial operator feedback

## Purpose

Capture short, actionable findings from hands-on StageFlow use without creating a new
approval workflow. Add one dated entry per observation and link a screenshot only when
it materially clarifies the issue. Never attach customer media, transcripts, credentials,
private paths, or raw Event artifacts.

## Classification

- **Green:** presentation, density, navigation, accessibility, missing read-only context,
  or terminology clarification that preserves accepted authority and lifecycle meaning.
  Implement directly in the relevant bounded UX plan.
- **Yellow:** changes Session, Stage, Package, Attention, persona, authority, automation,
  qualification, retention, or public-contract semantics. Record the evidence and route
  the exact decision for architecture/product review before implementation.
- **Red:** production deployment, irreversible data action, credentials, or another
  specifically protected external action. Record no secret material; obtain explicit
  action approval.

## Suggested entry

```markdown
### YYYY-MM-DD - concise finding

- Route/scenario:
- Display size/zoom:
- Category: glance comprehension | missing information | prominence | navigation |
  ergonomics | terminology | authority action | Editorial workflow
- Observation:
- Operational consequence:
- Recommended smallest change:
- Classification: Green | Yellow | Red
- Status: captured | implementing | validated | decision required
```

## Current findings

No operator findings are pending at this milestone baseline. Add new entries below this
line; preserve resolved entries as concise evidence rather than deleting them.

### 2026-09-27 - Owner direction: simplify for fast scanning under dense workload

- Route/scenario: Session Detail (`/sessions/[sessionId]`), live-run Session, kernel mode,
  ED-0093 review checkpoint.
- Display size/zoom: 1440 px wide, 100%.
- Category: glance comprehension | prominence
- Observation: the owner asked that the UI in general be simpler and easy to scan for a
  human worker, so that important information can be taken in quickly during dense
  workloads.
- Operational consequence: this is a standing design rule for ED-0093 and later phases:
  - lead with a one-line state and consequence summary;
  - raise exceptions, not repetition;
  - show a detail once, and collapse secondary evidence by default;
  - prefer readable labels over opaque identifiers;
  - never rely on colour alone.
- Recommended smallest change: the five findings below.
- Classification: Green (presentation and density; no authority or semantic change)
- Status: validated (ED-0093)

### 2026-09-27 - The Outputs panel is buried below the long evidence drill-down

- Route/scenario: Session Detail, live-run Session.
- Category: prominence
- Observation: the new Outputs panel starts about 12,000 px down, below the Media Timing
  Evidence drill-down.
- Operational consequence: a producer does not see the Assembly state, or whether it is
  approvable, without long scrolling.
- Recommended smallest change: put the Outputs panel directly after the Session's
  lifecycle and media summary, and collapse the evidence drill-down by default.
- Classification: Green
- Status: validated (ED-0093)

### 2026-09-27 - The media timing evidence drill-down is noisy

- Route/scenario: Session Detail, the "Media Timing Evidence" section (pre-ED-0093).
- Category: glance comprehension
- Observation:
  - each asset card repeats the same limitation phrases several times;
  - each card prints the full `ffprobe` SHA-256 tool identity twice;
  - every card is expanded.
- Operational consequence: the section dominates the page and hides the signal
  (qualification and candidate interval).
- Recommended smallest change:
  - show a collapsed-by-default section with a one-line summary (for example
    "11 assets · all unqualified · advisory only");
  - de-duplicate the limitations;
  - show the tool identity as a short hash prefix;
  - keep the full detail behind disclosure.
- Classification: Green
- Status: validated (ED-0093)

### 2026-09-27 - A repeated per-row warning hides the exceptions

- Route/scenario: Session Detail, Outputs → Assembly member order, and Media timing.
- Category: glance comprehension
- Observation: "Unqualified recorder timing" is printed on all 11 members, and again in
  Media timing (22 times).
- Operational consequence: repetition trains the eye to skip the warning, and an exception
  (such as a member on a `registration_time` fallback) would not stand out.
- Recommended smallest change: one summary line above the list (for example "All 11
  members ordered by unqualified recorder timing"), with only differing members flagged
  per row.
- Classification: Green
- Status: validated (ED-0093)

### 2026-09-27 - Members are identifiable only by UUID

- Route/scenario: Session Detail, Outputs → Assembly member order.
- Category: missing information | terminology
- Observation: rows read "Position N · Media <uuid>".
- Operational consequence: a producer cannot recognise which recording a row is.
- Recommended smallest change: a readable label built from data the UI already has, with
  no filenames or paths:
  - the position;
  - the wall-clock start;
  - the duration from the evidence interval, when known.

  The UUID moves to a secondary, copyable detail.
- Classification: Green
- Status: validated (ED-0093)

### 2026-09-27 - Media timing repeats the Assembly member list

- Route/scenario: Session Detail, Outputs → Media timing.
- Category: glance comprehension
- Observation: the Media timing list repeats every Assembly member with the same content.
- Operational consequence: redundant scrolling and reading.
- Recommended smallest change: fold the timing facts (start, duration, evidence revision)
  into the member rows. List separately only media outside the Assembly, such as
  unresolved or unplaced assets.
- Classification: Green
- Status: validated (ED-0093)

### 2026-09-27 - Second scanning pass after the first owner-review changes

- Route/scenario: Session Detail, live-run Session, kernel mode, after the first ED-0093
  review changes.
- Category: glance comprehension | prominence
- Observation (applying the owner's standing scanning rule):
  - Assembly member rows still take about three lines each, and repeat "Evidence
    revision 1 · frozen and latest" on all 11.
  - The Transcription Evidence section expands every transcript segment of every asset,
    making the page thousands of pixels long.
  - The collapsed "Media Timing Evidence · 8 assets" does not match the 11 members plus 1
    unresolved asset shown above it. It is a bounded recent sample.
  - The transcription operations grid shows 11 identical "succeeded" tiles.
- Operational consequence: long, uniform content hides the rare exception a worker must
  act on.
- Recommended smallest change:
  - a compact one-line-per-member table, with a shared evidence revision moved to the
    summary line and only differing values shown per row;
  - Transcription Evidence collapsed by default behind a summary (count complete, total
    words), with per-asset disclosure;
  - a truthful count label for the bounded evidence sample (for example "8 recent of 12");
  - operations summarized by state ("11 succeeded"), with tiles only for non-succeeded
    operations.
- Classification: Green (presentation only; no authority, command, or semantic change)
- Status: validated (ED-0093)
- Validation: frontend typecheck and lint passed; all 118 tests passed with each test
  file run separately using Node's `--test-isolation=none` sandbox workaround. The normal
  test runner and build worker hit `spawn EPERM`; host test/build checks remain required.
