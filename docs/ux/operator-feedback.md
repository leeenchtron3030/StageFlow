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

### 2026-09-27 - ED-0094 review checkpoint: action screens

- Route/scenario: Session Detail, validation Session, kernel mode. A live approve and a
  live render request were made through the UI; the render completed on the GPU.
- Category: glance comprehension | authority action | ergonomics
- Observation and owner-approved changes:
  1. Render operations and Rendered Outputs are four-line blocks headed by long UUIDs.
     Change: one compact table, newest first, with state, profile version, Assembly
     revision *number*, duration or frames, and produced time. IDs go in details.
  2. "Request render" stays the primary action when a render for the current revision is
     already pending or has succeeded. Change: show the render state for the current
     revision ("Render pending", "succeeded", or "failed"). Re-rendering becomes a
     deliberate secondary action.
  3. "Duration unknown" repeats on every row. Change: when it is uniform, state it once in
     the summary and hide the column.
  4. Slot bindings show packaging revision UUIDs. Change: show the Packaging Asset name
     and role from the existing packaging read, with the ID in details.
  5. The confirmation dialog repeats its heading under the consequence line. Change:
     remove the redundant heading.
  6. Opening the UI at `127.0.0.1` makes every command (Demo and capability) fail as
     `cross_site`, because the same-origin check compares text literally against
     `localhost`. Owner decision: treat `localhost`, `127.0.0.1` and `[::1]` on the same
     scheme and port as one origin. The check stays loopback-only, is tested explicitly,
     and has no other change.
- Classification: Green (items 1–5, presentation). Item 6 changes the same-origin check.
  The owner approved it explicitly on 2026-09-27, bounded to loopback aliases.
- Owner clarification for items 1–2: operations have no timestamp. Group them stably by
  state (pending/leased/running, then succeeded, then failed/other), without claiming
  chronology. Sort Rendered Outputs by `produced_at`, newest first within the bounded
  read. For the current revision, in-flight takes precedence over succeeded (with the
  newest matching output), then failed. This is frontend presentation only.
- Status: validated (ED-0094)
- Validation: 183/183 frontend tests passed with each file run separately using
  `node --import ./src/experience/server-test-runtime.ts --test --test-isolation=none`.
  Typecheck, lint and whitespace checks passed. The normal runner failed to spawn all
  15 test-file workers (`EPERM`); the build compiled successfully, then its TypeScript
  worker hit `spawn EPERM`. Host test/build completion remains required.
  Independent Codex review approved after the alias check was constrained to the
  original request host, with tests for Next.js normalization of other 127.x.x.x hosts.

### 2026-09-27 - Owner decision: Editorial origin labels

- Route/scenario: `/editorial` review queue and Session Detail moments (ED-0095).
- Category: terminology | glance comprehension
- Observation: "Declared" and "Derived" are internal provenance terms. They do not tell a
  producer at a glance whether a person or StageFlow created the moment.
- Owner decision: the UI labels the `declared` origin as **Marked** (a person marked the
  moment) and the `derived` origin as **Suggested** (StageFlow generated it, and it awaits
  human review). A Suggested row shows its source inline, for example
  `Suggested · "people"`.
- Unchanged: the canonical domain, storage, and API values (`declared` / `derived`), and
  the full provenance under Candidate details.
- Classification: Green (UI terminology only)
- Status: captured (to implement in ED-0095)

