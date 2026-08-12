# StageFlow Visual Design System & Interaction Density Specification

**Status:** Draft v0.1
**Source fidelity:** Exact provided draft.
**Applies to:** Producer and Editorial workspaces
**Primary environments:** MacBook Pro, external control-room display
**Default operating context:** Dark control-room-friendly interface
**Purpose:** Define StageFlow’s visual hierarchy, information density, operational emphasis, component behavior, and cross-persona design language before high-fidelity implementation.

> **Repository interpretation:** This Draft v0.1 is the shared visual and interaction
> language requirement for future Producer and Editorial surfaces. It does not implement
> frontend components, styling, tokens, responsive layouts, or runtime behavior.

---

## 1. Design Character

StageFlow should visually communicate:

**calm operational authority**

rather than:

* consumer media software,
* generic enterprise SaaS,
* developer monitoring tools,
* broadcast equipment skeuomorphism,
* traditional nonlinear editing software.

The design should combine:

**broadcast multiview discipline**

with:

**modern native-quality operational software.**

Key characteristics:

* dark by default,
* dense but breathable,
* high information-to-decoration ratio,
* stable geometry,
* restrained state color,
* minimal animation,
* strong typography,
* highly legible numerals,
* keyboard-first capability,
* clear provenance,
* calm healthy state,
* strong exception visibility.

---

## 2. Visual Priority Hierarchy

Every StageFlow screen should visually answer in this order:

1. **Where am I?**
2. **What is happening?**
3. **Does anything require me?**
4. **What consequence exists?**
5. **What can I do?**
6. **What evidence supports this?**
7. **What technical detail exists underneath?**

The visual hierarchy should mirror this operational hierarchy.

---

## 3. Control-Room Dark Mode

Default Event Mode should use a dark presentation suitable for:

* dim control rooms,
* backstage environments,
* extended viewing,
* adjacent production monitors.

Dark mode should not mean:

* pure black backgrounds,
* glowing neon borders,
* highly saturated status colors,
* cyberpunk styling.

Instead use layered dark neutral surfaces.

Conceptually:

```text
GLOBAL BACKGROUND
darkest

PRIMARY WORKSPACE
slightly raised

ROWS / PANELS
subtle separation

SELECTED / FOCUSED
clearly differentiated

INSPECTOR
stronger local hierarchy
```

The interface should remain readable in a normally lit office.

---

## 4. Light Mode

Light mode may be supported later for:

* daytime office review,
* post-event Editorial,
* accessibility/user preference.

The semantic visual hierarchy must remain identical.

Do not design dark mode using meanings that cannot translate to light mode.

---

## 5. Surface Hierarchy

Use a restrained surface system.

Recommended conceptual levels:

### Level 0 — Application background

Global shell.

### Level 1 — Primary workspace

Main operational area.

### Level 2 — Structured panel

Attention, Infrastructure, Candidate Inspector.

### Level 3 — Focused item / active inspector

Current selected Candidate, package problem, confirmation.

### Level 4 — Modal authority surface

Reserved for consequential authoritative confirmation.

Avoid deep stacking of decorative panels.

---

## 6. Borders

Borders should define structure quietly.

Prefer:

* thin separators,
* subtle contrast shifts,
* whitespace.

Avoid:

* rounded cards around every section,
* thick outlines,
* boxes nested inside boxes.

High-density operational UIs benefit from strong alignment more than decorative containers.

---

## 7. Corner Radius

Use restrained radius.

Primary operational rows and tables may have little or no visible rounding.

Focused controls/panels may use modest rounding.

Avoid highly rounded consumer-style cards and oversized pills.

---

## 8. Typography

Use a modern system/interface sans-serif with excellent:

* small-size rendering,
* numerals,
* weight differentiation,
* cross-platform availability.

Do not make brand typography dependent on a decorative display face.

Typography should remain functional during long Events.

---

## 9. Typographic Levels

Recommended conceptual hierarchy:

### Event / Workspace Identity

Strong but compact.

Example:

**DEVCON 202X**

### Primary Entity

Session / Stage / Candidate title.

Example:

**Future of Ethereum**

### Primary Operational State

Example:

**PRESENTATION ACTIVE**

### Secondary Context

Example:

Alice Smith · Example Foundation

### Operational Metric

Example:

`+39 sec`

### Evidence / Provenance

Smaller and quieter.

Example:

`DERIVED · Assembly Policy v3`

---

## 10. Numerals

Use tabular numerals wherever alignment matters.

Especially:

* elapsed time,
* wall-clock time,
* lag,
* media counts,
* Candidate counts,
* revisions,
* durations.

Example:

```text
14:04:18
14:42:31
+00:39
+04:18
```

Avoid visually jumping widths in live updating metrics.

---

## 11. Uppercase

Use uppercase sparingly for operational classifications:

* LIVE
* REVIEW REQUIRED
* DECLARED
* EXTERNAL
* RECOVERING

Do not use uppercase for large paragraphs or ordinary labels.

---

## 12. Density

StageFlow should use a compact operational density.

Rows must be:

* easy to scan,
* large enough for reliable pointing,
* not oversized like consumer settings screens.

The default density should favor fitting meaningful Event state on a MacBook without requiring excessive scrolling.

---

## 13. Density Modes

Potential future preference:

* Comfortable
* Operational

But initial implementation should choose one deliberate operational density.

Do not create density settings before real use demonstrates the need.

---

## 14. Spacing Rhythm

Use a small consistent spacing scale.

Conceptually:

* micro: icon ↔ label
* compact: fields within a row
* standard: row padding
* section: between operational groups
* major: between workspace regions

Avoid arbitrary spacing differences.

Alignment should create most of the structure.

---

## 15. Column Alignment

Mission Control and dense Session/Queue screens should strongly align columns vertically.

Example:

```text
STAGE        SESSION                 MEDIA      INTEL       STATE

Main         Scaling Ethereum        18s        ✦5          LIVE
Stage B      Future of Ethereum      22s        ✦8 ◆2       LIVE
Stage C      Protocol Design         —          ✦3          REVIEW
```

Stable columns improve peripheral scanning.

---

## 16. Row Selection

Selection is a navigation state.

It must not visually resemble:

* warning,
* critical condition,
* approval,
* live state.

Selected rows should remain obvious under keyboard focus and pointer interaction.

---

## 17. Hover

Hover is supplementary.

It may reveal:

* secondary navigation affordance,
* quick context action.

Essential status must always remain visible without hover.

---

## 18. Keyboard Focus

Keyboard focus should be stronger than hover.

Focus treatment must work:

* across dark surfaces,
* over selected rows,
* on timeline markers,
* on buttons,
* inside inspectors.

Keyboard users must always know where the next action will occur.

---

## 19. Status Color Philosophy

Color answers:

**How much attention does this deserve?**

It should not attempt to encode every domain state.

Conceptual semantic groups:

### Neutral

Healthy normal state.

### Informational / Active

Selection, active Session, live context.

### Review

Ambiguity or human judgment required.

### Intervention

Immediate operational action required.

### Completion

Explicit approval/completion where useful.

Use text + icon + position in addition to color.

---

## 20. Healthy State

Healthy operational information should primarily use neutral typography.

Example:

```text
Media
Healthy
```

Do not fill the row green.

This makes warnings materially more visible.

---

## 21. Live State

LIVE should have recognizable but restrained emphasis.

It must not blink continuously.

Possible treatment:

* compact indicator,
* clear text,
* small steady live dot.

LIVE means:

**currently happening**

not:

**healthy**

or:

**caught up.**

---

## 22. Review State

Review state should be highly noticeable but not visually alarming.

Example:

```text
REVIEW REQUIRED

1 media item unresolved
```

The user should interpret:

**I need to look at this**

not:

**the system is failing.**

---

## 23. Intervention State

Intervention styling should be reserved for meaningful active operational consequence.

Examples:

* authoritative backend unavailable,
* Stage source unavailable with capture consequence,
* material media-risk condition.

This scarcity gives the visual state credibility.

---

## 24. Approval State

Approval/completion should generally become quieter once settled.

Example:

```text
PACKAGE
Complete · revision 3
```

A large celebratory success treatment is unnecessary.

---

## 25. State Chips

Good chip examples:

`LIVE`

`REVIEW REQUIRED`

`EXTERNAL`

`AUTO-APPROVED`

`DEFERRED`

Bad approach:

```text
[ MEDIA ] [ HEALTHY ] [ 22 SEC ] [ SESSION ] [ ACTIVE ]
```

Do not transform data into pill soup.

---

## 26. Icons

Icons should reinforce familiar operational semantics.

Use icons for:

* attention,
* Candidate origin,
* approval,
* revision/history,
* external context,
* worker/processing,
* playback.

Avoid novel icons where text would be clearer.

Every critical icon requires accessible text/tooltip.

---

## 27. Moment Marker Grammar

Provisional timeline grammar:

### Machine Candidate

`✦`

Meaning:

StageFlow-generated Editorial Candidate Moment.

### Human Producer Mark

`◆`

Meaning:

Producer-declared Moment Candidate.

### Editorial Approved

`✓`

Meaning:

Editorial decision accepted.

### Editorial Rejected

`×`

Meaning:

Editorial decision rejected.

These are conceptual markers.

Final icons may change.

Origin must remain visible through text/provenance.

---

## 28. Boundary Grammar

Authoritative boundaries should be visually stronger than proposals.

Concept:

```text
DECLARED START
│
▼
──────────────── Session ────────────────
                                      ▲
                                      │
                                 DECLARED END
```

Proposals:

* lighter line,
* dashed marker,
* clear PROPOSED label.

Never make proposed and authoritative boundaries visually interchangeable.

---

## 29. External Context Grammar

Program Expectation should appear visually secondary.

Example:

```text
EXTERNAL

Expected
14:00
```

Realized Session:

```text
DECLARED

Started
14:04:18
```

The difference should remain clear even at a glance.

---

## 30. Timeline Base

The timeline should use a simple linear base with strong time-position mapping.

Avoid decorative waveforms as the default unless they serve an actual editing task.

Producer timeline:

* media segments,
* boundaries,
* unresolved/conflict,
* continuity,
* secondary Moment markers.

Editorial timeline:

* media continuity,
* Candidate markers,
* Producer marks,
* Editorial decisions,
* transcript/topics later.

---

## 31. Timeline Zoom

Initial Producer Package Review may require:

* fit Session,
* moderate zoom around issue.

Editorial needs greater temporal exploration.

Useful concepts:

* Fit Session
* Fit Candidate
* ±30 sec context
* manual zoom later

Do not build NLE-grade zoom/pan complexity prematurely.

---

## 32. Timeline Selection

Selected Candidate or media issue should create a strong shared vertical playhead/reference.

This should synchronize:

* video,
* transcript,
* timeline,
* Inspector.

---

## 33. Playhead

Editorial playhead should be visually dominant over Candidate markers but not overpower the whole screen.

Current time should remain legible at all times.

---

## 34. Media Segments

Producer Package Review may represent recording segments as adjoining blocks.

Segments should communicate:

* ownership,
* temporal coverage,
* unresolved state,
* conflict.

Do not imply individual media files are individually important when the Session package is what matters.

---

## 35. Unplaced Media

Interval-less media should never be fabricated onto the timeline.

Use a clear secondary lane:

**UNPLACED / TIME UNKNOWN**

This should look intentionally separate, not like an error rendering.

---

## 36. Gap Presentation

Potential gap:

```text
POTENTIAL GAP
00:41
```

Avoid dramatic broken-timeline graphics unless evidence indicates material loss.

Wording should preserve epistemic truth.

---

## 37. Candidate Inspector

Editorial Candidate Inspector should use a stable hierarchy:

1. Candidate identity/state
2. time/range
3. transcript excerpt / content
4. provenance/reasons
5. participant context
6. actions
7. deeper technical details

Approve/Reject/Defer must remain visually prominent.

---

## 38. Producer Attention Inspector

Producer-focused inspector hierarchy:

1. consequence
2. affected Stage/Session
3. what StageFlow knows
4. what continues safely
5. required decision
6. evidence
7. technical diagnostics

This differs intentionally from Editorial.

---

## 39. Primary Actions

One primary action per focused decision.

Examples:

* START SESSION
* END PRESENTATION
* REVIEW ASSOCIATION
* APPROVE PACKAGE
* APPROVE MOMENT

Secondary actions remain visually subordinate.

---

## 40. Destructive vs Authoritative

Not every authoritative action is destructive.

For example:

**START SESSION**

is consequential but not destructive.

Confirmation styling should communicate:

**This changes authoritative truth**

rather than:

**Danger.**

Reserve destructive styling for actual destructive operations.

---

## 41. Confirmation Panels

Consequential confirmations should display:

* entity,
* effective time,
* current fact,
* fact that will become authoritative,
* consequence.

Example:

```text
DECLARE PRESENTATION END

Future of Ethereum
Stage B

Effective time
14:42:31

This becomes the authoritative
presentation end.
```

---

## 42. Disabled Buttons

Disabled action must include nearby explanation.

Example:

```text
APPROVE PACKAGE
Unavailable

1 unresolved media item remains.
```

A tooltip alone is insufficient for a primary workflow block.

---

## 43. Empty States

Healthy operational empty states should be extremely simple.

Producer:

```text
NO PRODUCER WORK WAITING

Event operation is healthy.
```

Editorial:

```text
CAUGHT UP

No priority Candidates waiting.
```

No illustrations required.

---

## 44. Loading State

Initial loading should preserve expected geometry where possible.

Avoid skeleton animations on continuously updating operational surfaces if they imply meaningful content.

For reconnect/reconciliation, explicit state language is more important than generic loading spinners.

---

## 45. Reconnecting

Example:

```text
RECONNECTING

Last authoritative update
14:31:42
```

Displayed data is visibly stale.

---

## 46. Recovering

Example:

```text
RECOVERING

Connection restored.
Fresh reconciliation required.

Authoritative actions remain disabled.
```

Recovering should look materially different from loading.

---

## 47. Worker State

Producer-facing worker presentation:

```text
MOMENT DETECTION
+41 sec behind

AI Worker 01
Processing
```

Diagnostics may expand:

```text
GPU utilization
87%

VRAM
10.8 / 16 GB
```

Never reverse this hierarchy.

---

## 48. Infrastructure Panel

Infrastructure should remain compact.

Example:

```text
INFRASTRUCTURE

PostgreSQL       Ready
Stage Sources    6 / 6
AI Workers       2 / 2
Moment lag       +39s max
```

Infrastructure is a supporting strip, not Mission Control's primary visual.

---

## 49. Producer Persona Character

Producer workspace should feel:

* structured,
* stable,
* Stage-oriented,
* operational,
* slightly denser,
* more tabular.

Primary visual anchors:

* Stage rows,
* operational state,
* attention,
* authoritative action.

---

## 50. Editorial Persona Character

Editorial should feel:

* temporal,
* media-centered,
* contextual,
* slightly more exploratory,
* richer in transcript/content.

Primary visual anchors:

* media,
* timeline,
* Candidate Inspector,
* transcript,
* review actions.

It should still visibly belong to StageFlow.

---

## 51. Shared Persona Elements

Producer and Editorial share:

* shell,
* typography,
* spacing,
* state language,
* buttons,
* focus treatment,
* provenance,
* revision presentation,
* timeline fundamentals,
* stale/recovery treatment.

They should not feel like unrelated applications acquired from different vendors.

---

## 52. Persona Transition

Switching Producer → Editorial should change:

* navigation context,
* workspace density,
* information priority,

without changing:

* Event identity,
* Session identity,
* basic visual vocabulary.

A user should immediately understand:

**same Event, different job.**

---

## 53. Navigation Rail

Provisional hierarchy:

```text
PRODUCER

Mission Control
Event
Sessions       3
Infrastructure

──────────────

EDITORIAL

Live Triage
Review Queue
Approved
```

Current persona gets stronger grouping.

Other persona remains available but visually quieter.

---

## 54. Navigation Count Semantics

Counts must be meaningful.

Producer:

`Sessions 3`

only if that number represents unresolved Producer work.

Better naming may be:

`Work 3`

if ambiguity exists.

Editorial:

`Review 8`

means eight relevant unreviewed items according to current scope.

Never use generic unread notifications counts.

---

## 55. Workspace Header

Workspace header should identify:

* workspace,
* current Event,
* optional scope/filter,
* meaningful lag/attention state.

Avoid duplicate global navigation.

---

## 56. Mission Control Header

Example:

```text
DEVCON 202X

ACTIVE · 6 STAGES

No intervention required
```

or:

```text
DEVCON 202X

ACTIVE · 6 STAGES

2 items require review
```

---

## 57. Editorial Header

Example:

```text
EDITORIAL · DEVCON 202X

Live Triage

Review lag
+2m 18s
```

Review lag should not be styled as critical by default.

---

## 58. Session Header

Shared pattern:

```text
Future of Ethereum

Alice Smith · Example Foundation

Stage B
```

Then role-specific state below.

Producer:

`Presentation Active`

Editorial:

`Source Package · revision 2`

---

## 59. Panels

Panel titles should be terse:

* ATTENTION
* INFRASTRUCTURE
* PACKAGE CHECKS
* TRANSCRIPT
* CANDIDATE
* HISTORY

Avoid verbose card headings.

---

## 60. Section Labels

Use labels for grouping rather than decorative boxes.

Example:

```text
PREVIOUS    CURRENT    NEXT
```

The alignment itself carries meaning.

---

## 61. Progressive Disclosure

Every detailed object should support approximately:

### Level 1

Operational summary.

### Level 2

Workflow details.

### Level 3

Evidence/provenance.

### Level 4

Technical implementation details.

Users should rarely need Level 4 during normal Event operation.

---

## 62. Evidence Visual Language

Evidence types may be represented with subtle labels:

```text
DECLARED
Producer mark

INFERRED
Semantic significance

OBSERVED
Speaker emphasis
```

Avoid giant colored provenance blocks.

---

## 63. History Visual Language

History should use calm chronological presentation.

Example:

```text
15:12:04
Producer approved package revision 2

15:48:19
Relevant media discovered

15:48:20
Package revision 3 opened
```

Historical state is read-only.

---

## 64. Revision Emphasis

Current revision always strongest.

Previous approval remains visible but secondary.

Example:

```text
PACKAGE

Revision 3
REVIEW REQUIRED

Previous

Revision 2
Approved 15:02
```

---

## 65. Automation Visual Language

Automation success should look routine.

Example:

```text
AUTO-APPROVED

Main Stage Completion v2.1
```

Automation withheld should look like a normal review condition:

```text
REVIEW REQUIRED

Automatic approval withheld.

1 media item unresolved.
```

Avoid robot/AI iconography.

---

## 66. AI Visual Language

StageFlow should not make AI a visual brand gimmick.

Do not decorate every machine-derived element with:

* sparkles,
* gradients,
* robot icons.

Use epistemic/provenance language.

Moment Candidate marker may use a distinct symbol, but the product remains operational software.

---

## 67. Moment Candidate Strength

Possible presentation:

* Priority
* Strong
* Candidate

But this should remain secondary to provenance and human marks.

Avoid false precision.

---

## 68. Producer Mark Strength

Producer mark should be strongly identifiable because it is human-declared during live operation.

However, it should not automatically use critical alert styling.

It is editorial priority, not production danger.

---

## 69. Editorial Approved Moment

Approval styling should provide a clear settled state while remaining visually calm.

Example:

```text
APPROVED

Editorial Clip created
```

---

## 70. Transcript Typography

Transcript should optimize reading and seeking.

Use:

* comfortable line height,
* clear timestamps,
* subtle speaker labels,
* strong current-playback highlight.

Do not resemble a code editor.

---

## 71. Transcript Current Line

Current playback line should remain visible with a clear but quiet highlight.

Candidate-range transcript may use a secondary background/edge indicator.

---

## 72. Transcript Search

Search highlights should not visually compete with:

* current playback,
* Candidate range,
* selected text.

Each needs distinct semantics.

---

## 73. Media Viewer

Editorial media viewer should feel functional.

Controls appear on interaction or remain in a compact persistent control strip.

Avoid large consumer-video overlays.

---

## 74. Playback Controls

Prioritize:

* play/pause,
* skip context,
* speed,
* current time,
* loop Candidate,
* return live.

Secondary controls can remain hidden.

---

## 75. Near-Live Indicator

Example:

```text
LIVE

6m 12s behind
```

The word LIVE indicates source Session status.

The lag indicates the editor's review position.

---

## 76. Candidate Queue Density

Candidate rows should fit enough items to maintain context.

Each default row may include:

* origin marker,
* Session time,
* short excerpt,
* priority/state.

Do not place full evidence lists in queue rows.

---

## 77. Producer Work Queue Density

Work Items may be slightly taller than Session rows because consequence/reason matter.

But they should still remain scan-friendly.

---

## 78. Responsive Strategy

Do not shrink desktop layout proportionally.

Instead collapse in priority order.

MacBook:

* retain primary entity/state/action,
* move secondary panels below or into drawers,
* convert side-by-side inspectors to tabs where necessary.

---

## 79. Producer MacBook Priority

Preserve:

1. Stage matrix
2. attention state
3. authoritative action
4. key consequence
5. infrastructure summary
6. technical details

---

## 80. Editorial MacBook Priority

Preserve:

1. media
2. timeline
3. current Candidate
4. review actions
5. transcript
6. Candidate queue
7. deeper provenance

Transcript and Inspector may use tabs if needed.

---

## 81. External Display Strategy

Use added space for **simultaneous context**, not larger typography.

Producer may show:

* Stage matrix,
* Attention,
* Infrastructure,
* selected Stage context.

Editorial may show:

* media,
* timeline,
* transcript,
* Candidate Inspector,
* Candidate queue.

---

## 82. Minimum Width Philosophy

Below a practical laptop width, StageFlow should progressively collapse secondary context.

Do not attempt to preserve full control-room density on tablet/mobile.

Mobile is not a primary Event-control target.

---

## 83. Motion

Allowed motion:

* subtle new-item arrival,
* progress indicator where progress exists,
* live indicator,
* panel transition.

Avoid:

* continuously animated gauges,
* bouncing alerts,
* pulsing success states,
* decorative transitions.

---

## 84. Sound

StageFlow should not depend on sound alerts by default.

Future optional audio cues may be appropriate for:

* critical intervention,
* Producer mark in Editorial,

but only with explicit user configuration.

The production environment is already acoustically complex.

---

## 85. Alert Persistence

Information:

may expire or remain in activity history.

Review:

persists until resolved/superseded.

Intervention:

persists while consequence exists.

Do not require humans to manually dismiss resolved operational truth.

---

## 86. Toasts

Toasts should confirm lightweight actions:

* Moment marked
* Candidate deferred
* filter saved later

Do not put significant operational conditions exclusively in toasts.

---

## 87. Modal Use

Use modal/authority panels only when:

* declaring Session start/end,
* approving package,
* consequential destructive operation later.

Do not use modals for routine navigation or Candidate inspection.

---

## 88. Drawer Use

Drawers are suitable for:

* compact Infrastructure detail,
* evidence/provenance,
* Work Queue on narrower layout,
* secondary Session metadata.

Avoid drawer nesting.

---

## 89. Inspector Use

Inspector is preferred for:

* Candidate detail,
* media association evidence,
* automation provenance,
* revision impact.

This preserves main workspace orientation.

---

## 90. Accessibility

Operational density must still support:

* keyboard-only operation,
* visible focus,
* screen-reader labels,
* color-independent meaning,
* contrast,
* scalable text,
* reduced-motion preference,
* meaningful ordering.

---

## 91. Cognitive Accessibility

Use stable vocabulary.

If a state is called:

**Review Required**

in Mission Control, do not call equivalent state:

**Needs Attention**

elsewhere unless the distinction is intentional.

Consistency reduces Event-day cognitive load.

---

## 92. Copy Tone

Operational copy should be:

* factual,
* concise,
* calm,
* specific.

Good:

**1 media item cannot be safely assigned. Media is preserved.**

Bad:

**Oops! We ran into a problem while processing your media.**

StageFlow is professional production software.

---

## 93. Technical Copy

Technical detail may be precise.

Example:

```text
PostgreSQL
Unavailable

Last successful reconciliation
14:31:22
```

But default copy still explains consequence:

**Authoritative actions paused.**

---

## 94. Icon + Text Rule

Critical state/action must always have text.

Icon-only controls should be limited to familiar low-risk actions such as playback where tooltip/accessibility support exists.

---

## 95. Status Ordering

Within a row:

Identity first.

Then current operational state.

Then supporting metrics.

Then secondary context.

Then action.

Do not lead with an icon or count before the entity name.

---

## 96. Visual Noise Budget

Every saturated color, badge, icon, divider, animation, and persistent metric spends attention.

StageFlow should deliberately maintain an attention budget.

The interface is successful when:

healthy Event operation looks almost boring.

---

## 97. Producer Visual Success Test

A Producer looking away at the show and then back to StageFlow should reacquire the state of the Event immediately.

They should not need to:

* reread every row,
* interpret charts,
* dismiss notifications,
* remember what changed position.

---

## 98. Editorial Visual Success Test

An editor moving between Candidate Moments should retain:

* Session identity,
* temporal location,
* current review state,
* provenance,
* available actions

without losing media/transcript orientation.

---

## 99. Cross-Persona Success Test

A user moving Producer → Editorial should immediately recognize the same:

* Event,
* Session,
* state vocabulary,
* timeline grammar,
* provenance language.

But the workspace should clearly optimize for a different human responsibility.

---

## 100. Design Principle

**Quiet when certain.**

**Clear when uncertain.**

**Explicit when authority changes.**

**Detailed only when requested.**

That should be the defining visual behavior of StageFlow.
