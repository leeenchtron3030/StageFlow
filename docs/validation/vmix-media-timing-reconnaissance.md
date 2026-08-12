# vMix media timing evidence reconnaissance

## Status and authority

**Completed Green reconnaissance; qualification-only evidence.** This document records a
read-only inspection of the media retained for Run 004. It does not revise Run 004,
qualify recorder metadata as production truth, or authorize Session/media-association
behavior.

Inspection used the locally supplied vMix FFmpeg 6.0 executable. No media was decoded,
transcoded, renamed, or modified. The 49 external MP4 files and Run 004 JSON/Markdown,
database, configuration, and locks remain unchanged and outside Git.

## Question

Does the retained corpus contain timing evidence useful enough to justify a controlled
calibration experiment and a provider-neutral production design decision?

**Finding: yes for calibration and architecture work; no for production authority.**

## Sanitized corpus observations

| Observation | Result | Epistemic status |
| --- | --- | --- |
| Media count | 49 MP4 files | Observed |
| Total bytes | 19,911,596,787 | Observed |
| Container family | MOV/MP4 family; `mp42`, minor 0, compatible `mp41isom` | Observed |
| Video | H.264 High, 1920×1080, 29.97 fps; time base 1/29970 | Observed |
| Audio | AAC LC, stereo, 48 kHz; time base 1/48000 | Observed |
| Container start | 0 for every file | Observed |
| First video timestamp | 0–33 ms; DTS 0 for every file | Observed |
| First audio timestamp | PTS/DTS 0 for every file | Observed |
| Embedded creation time | Aware UTC on every file, exactly 60 seconds apart | Observed |
| Container duration | Approximately 60.01–60.03 seconds; final file 21.87 seconds | Observed |
| Filesystem creation/change lag from embedded anchor | 0.123–0.463 seconds | Derived comparison of observed proxies |
| Filesystem modification lag from candidate end | 0.290–0.373 seconds | Derived comparison of observed proxies |

The embedded sequence begins at `2026-08-12T00:51:01Z` and advances by exactly 60 seconds
per media item. Adding each observed container duration to its embedded creation time
produces a deterministic **candidate** interval. The calculation is reproducible, but its
meaning is unqualified: it does not establish whether the embedded anchor denotes command
time, mux start, first encoded sample, or useful-content start.

Nominal adjacent container intervals overlap by roughly 10–30 ms, and encoded audio
packet ranges produce roughly 10.6–32 ms arithmetic overlaps. These are arithmetic
residuals, not evidence of duplicated content or editorial continuity.

## Run 004 geometry

Using sanitized sequential media references and the unqualified candidate intervals:

| Relationship to durable Session boundaries | Media references |
| --- | --- |
| Before Session A | `media-00000`–`media-00001` |
| Across Session A start | `media-00002` |
| Inside Session A | `media-00003`–`media-00029` |
| Across Session A end | `media-00030` |
| Durable turnover gap | `media-00031`–`media-00032` |
| Across known-late durable Session B start | `media-00033` |
| Inside Session B | `media-00034`–`media-00047` |
| Across Session B end | `media-00048` |

Existing Run 004 association outcomes were `media-00000`–`media-00031` associated with A
and `media-00032`–`media-00048` unresolved. The geometry does not prove those outcomes
content-correct. In particular, the operator established that the durable B start was
late relative to substantive content, while the exact real start is absent from durable
Run 004 evidence.

## Interpretation

The corpus contains strong evidence of a stable recorder convention: monotonic UTC tags,
consistent zero-based streams, and durations that can be combined into reproducible
candidate intervals. It does **not** contain the independent ground truth needed to
interpret the convention or quantify its error relative to useful content.

Consequently:

- raw container, stream, packet, and filesystem facts remain Observed evidence;
- creation-time-plus-duration intervals remain Derived, unqualified candidates;
- recorder semantics remain Inferred and unaccepted;
- Run 004's lifecycle/preservation/policy PASS and association INCONCLUSIVE result stand;
- neither candidate intervals nor adjacency residuals may drive Session boundaries,
  association, package membership, or automation.

The controlled experiment in
[vMix media timing calibration](vmix-media-timing-calibration.md) is the next evidence
step. Production ownership and consumption remain the Yellow decisions in the
[accepted Media Timing Evidence architecture](../architecture/media-timing-evidence.md).
