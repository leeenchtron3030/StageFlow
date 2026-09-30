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
- Status: validated (ED-0095)

### 2026-09-27 - Owner decision: plain-language UI wording across Producer and Editorial screens

- Route/scenario: Session Detail (lifecycle, recordings, Outputs, media timing, Session
  tools, transcript), `/editorial`, the navigation, and the top bar.
- Category: terminology | glance comprehension
- Observation: internal domain and implementation terms appear throughout the UI.
  Examples: qualification and advisory, bounded, projection and Kernel, the association
  states, revision bookkeeping, slot bindings, candidate, and wall-clock. They hide what a
  producer needs to know.
- Owner decision (every recommended change was approved): one central UI-label mapping
  from each internal term to plain UI wording. Internal values stay visible under
  "Details" for diagnosis. The approved wording:
  - **Evidence certainty:**
    - "Recorder time (unverified)" replaces unqualified timing. Show nothing when the
      term does not apply.
    - "Estimate" replaces advisory, where it is not redundant.
    - "Estimated start: HH:MM:SS" replaces the derived candidate start.
    - Limitation text moves into details as "Recorder start and length are unverified".
    - Evidence revisions appear only in details, plus the exception "A newer timing
      estimate exists".
    - "not content truth" disclaimers move into details or are removed.
  - **Implementation words:**
    - "bounded ..." becomes "Latest N" or "Showing N of M", or is omitted.
    - "Live Kernel status · read only · Backend projection" becomes "Live · connected".
    - "Trusted Demo LAN · bounded live projection · Session workspace" becomes "Session
      tools".
    - "Stage aggregate context" and "Media membership · Aggregate" become "Recordings".
    - "Evidence only · not Session transcript truth" becomes "Automatic transcript: may
      contain errors".
  - **Assignment states:** Registered, Associated, Stabilizing, Unresolved, Conflicting
    become Found, In this Session, Still recording, Needs a decision, Claimed by two
    Sessions.
    - The unplaced-media notice becomes "1 recording needs a decision: no Session fits
      it. Nothing was deleted."
    - The association-reason text becomes "No Session matches this recording's time.
      Checked: [Session titles]."
  - **Bookkeeping:**
    - Revision numbers move into details, except where they explain a problem.
    - "Staleness: Current · Inputs unchanged" becomes "Up to date", or "Out of date: ..."
      when it applies.
    - "Frozen proposal order" becomes "Order locked when proposed".
    - The lifecycle badge "DECLARED" becomes "Set by producer".
    - Render states become "Rendering... / Done / Failed", and the profile becomes "1080p
      (v2)".
  - **Assembly:**
    - Slot bindings become "Layout: Intro ([asset name]) -> Recording".
    - The ordering explanation becomes "Ordered by recorder time", with an exception line
      such as "N recordings ordered by arrival time (no recorder time)" only when it
      applies.
  - **Editorial:**
    - Candidate becomes Moment ("Review moment", "Details").
    - "Point mark · Range needed" becomes "Single point: set start and end".
    - Range inputs become "time into Session (mm:ss)".
    - Navigation and page share one name: "Editorial review".
    - Origin labels are Marked / Suggested (see the previous entry).
  - **Top bar:** "Demo Profile · Single Stage · Not Event-Readiness Certified" becomes
    "Test setup · 1 stage · not event-ready". The not-event-ready disclaimer must stay.
- Unchanged: canonical domain, storage, and API terms, and every safety or honesty
  meaning. Only wording changes. A disclaimer is reworded, never dropped.
- Classification: Green (UI terminology and presentation)
- Status: validated (ED-0095)


### 2026-09-27 - ED-0099 review checkpoint: render quality

- Route/scenario:
  - the Event page (`/event`) and Session Detail on the render validation Event, in kernel
    mode;
  - quality chosen twice through the UI (1080p High at 16 Mbit/s, then 720p Compact);
  - the "Render again at current quality" confirmation opened on a Session whose outputs
    are 1080p Standard.
- Category: glance comprehension | prominence | terminology
- Observation and owner-approved changes:
  1. **Styling.** The Render quality section does not match the other Event panels: it
     has no kicker-and-title header, cramped inline controls whose labels run together,
     and unpadded history rows. Change: the same panel header as Authority and Attention,
     one control per row with its label above, and a padded history list.
  2. **Provenance line.** The "Chosen by" line shows a raw operator UUID and a raw ISO
     timestamp. Change: the summary line reads "Chosen 10:17 PM" in local time. The
     operator ID and the full timestamp move into a Details disclosure, as for other
     evidence.
  3. **Unexplained action.** "Render again at current quality" does not say what changed.
     Change: one line next to the action, for example "Latest output: 1080p Standard ·
     Current setting: 720p Compact".
  4. **320 kbit/s audio choice.** 1080p High's 320 kbit/s choice measured 261 kbit/s in
     [Run 004](../validation/results/render-durable-operation-004.md), because the native
     AAC encoder undershoots. Owner decision: keep the choice, labelled "up to 320
     kbit/s". There is no catalog change.
- Unchanged: the confirmation that names the quality (validated), the collapsed history,
  consequence-first wording, and all command, concurrency and authority behaviour.
- Classification: Green (presentation and wording)
- Status: validated (ED-0100)

### 2026-09-29 - ED-0108 review checkpoints: boundary cue phrases

- Route/scenario:
  - the Event page (`/event`) on the render validation Event, in kernel mode;
  - the *Conference stage* profile composed through the UI. "my name is" was removed, a
    custom start phrase was added, and it was published as version 1;
  - edits without publishing: removing "welcome back" then ticking Broadcast, and
    switching to the *Film or studio set* profile.
- Category: glance comprehension | repetition | honesty | recoverability
- **First checkpoint.** Observations; the owner approved all six changes:
  1. **Long group list.** All 21 groups were shown flat. Change: the ticked groups come
     first, and the others fold under "More groups" by category, with the regional
     add-ons separate.
  2. **Repeated badges.** Every phrase row repeated its group and evidence badge on a
     second line. Change: phrases are grouped under their first source group, one
     compact row each, with an "also in N other groups" note. One legend line replaces
     the repeated badge, and badges now appear only for the exceptions ("from published
     scripts", ⚠).
  3. **Removal could not be undone.** Change: a collapsed "Removed · N" list with Add
     back, which restores the phrase to every source group.
  4. **⚠ was missing on default noisy phrases** such as studio "moving on". Change: ⚠
     follows the catalog evidence label, not only the opt-in flag.
  5. **Profile name after edits.** The summary kept the profile name after the selection
     changed. Change: it reads "Custom (based on <profile>)", for drafts and for stored
     compositions.
  6. **Removed phrases returned.** Ticking another group brought a removed phrase back.
     Change: the removal persists, with the notice "N removed phrases stay removed".
- **Second checkpoint:** the owner approved the result. Two small fixes were made after
  review:
  - singular wording for one removed phrase;
  - re-adding a removed phrase as a custom phrase takes it out of Removed.
- Noted, not changed: moving a group between the selected list and "More groups" moves
  keyboard focus, as a consequence of item 1.
- Unchanged: the confirmation before publishing and before a profile switch, the history
  under Details, honest evidence wording, and all proxy, audit and authority behaviour.
- Classification: Green (presentation and wording)
- Status: validated (ED-0108)

### 2026-09-29 - ED-0110 review checkpoint: suggested presentations

- Route/scenario:
  - the Stage page (`/stages/main`) and Mission Control, in kernel mode;
  - two locally seeded synthetic review Events. Both have generic test-pattern talks with
    silent changeover cards and anonymous "Talk 1…5" schedules printed early. Both were
    run through the real discovery, timing and segmentation pipeline;
  - on each: suggest, confirm one, adjust and confirm one, reject one, set a producer
    offset, suggest again.
- Category: prominence | repetition | honesty | recoverability
- **Before the owner review (reviewer and live check):**
  - the panel was moved up under the Stage summary, from below the evidence block;
  - same-day ranges show the date once;
  - compact rows with grouped actions;
  - a styled Mission Control "Suggestions to review" strip;
  - singular and plural wording;
  - "Add the schedule first" for Stages with no schedule;
  - "Suggest again" only after a run.
- **Owner review, approved with one change:** the "Offset set by producer" badge
  repeated on every row. It now shows only on rows whose offset differs from the one in
  the summary.
- **Findings recorded, not changed here:**
  1. **Suggest again re-suggests decided talks.** A new run re-suggests talks that
     already have a Session, and talks that were rejected. Owner decision: planned as a
     small backend follow-up (ED-0111).
     - talks with a Session are left out and shown as "already a Session";
     - rejected talks may be suggested again.
  2. **Recording start beats short changeovers.** The recording's start boundary
     (strength 30) outscores a short real changeover. So the first talk's start snaps to
     the recording start, and on short, evenly spaced talks the offset estimate can
     alias by one talk (measured: 14 min estimated against 6 min true). This is a policy
     follow-up candidate.
  3. **Recordings are not re-matched after a confirm.** Media association still reports
     "No Session matches this recording's time" after confirming. This behaviour
     predates ED-0110 and is out of scope.
- Unchanged: confirming one suggestion at a time with an explicit step, no batch
  confirm, idempotent retries, honest estimate wording, and the proxy allowlist and audit.
- Classification: Green (presentation and wording)
- Status: validated (ED-0110)

### 2026-09-30 - ED-0113 review checkpoints: suggested boundaries

- Route/scenario:
  - Session Detail and the Stage page on the locally seeded synthetic review Event, in
    kernel mode;
  - Talk 3 confirmed with deliberately rough times, then Suggest again. Proposals matched
    the offsets exactly (start −3 min, end +2 min). Talk 2's earlier 1 min adjustment
    was also proposed;
  - Apply one, Dismiss one, then Suggest again: the dismissal stuck, and the applied edge
    was not re-proposed.
- Category: prominence | repetition | recoverability
- **First checkpoint.** The owner approved four changes:
  1. **Stage page.** Since ED-0111, realized talks are not listed in new runs, so the
     planned badge on Decided rows never appeared. Change: the summary gains "· N
     boundary suggestions", and a collapsed **Already Sessions** list gives one linked
     row per realized talk, with a badge when a proposal is open.
  2. **Session Detail repetition.** Rows repeated the date, the year and the signed
     difference. Change: the sentence plus "10:51:30 → 10:48:30", with the date only
     when it differs, and accessible labels. The confirmation step uses the same form.
  3. **Decision history** showed raw values. Change: readable rows such as "Start applied
     · 22:25 · by producer", with IDs one level deeper. This needed a small additive
     backend field (`boundary_kind` in history), which the owner approved at a Yellow
     stop.
  4. **Retry** was offered after deterministic refusals. Change: those show Refresh
     only; retry is kept for transport failures, 5xx and unknown outcomes.
- **Second checkpoint:** approved, with one polish. Already Sessions rows now use the same
  range format as the suggestion rows ("Sep 29, 10:00–10:26").
- Unchanged: Apply and Dismiss each have a confirmation step, there is no batch apply,
  retries stay idempotent, and the honest wording is kept.
- Classification: Green (presentation and wording; one owner-approved additive API field)
- Status: validated (ED-0113)
