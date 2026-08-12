# Real-Event Playback Validation Run 004

## Disposition

- **PASS — same-Stage Session lifecycle execution, with authority timestamp-quality
  caveat**
- **PASS — real-media preservation and conservative ambiguity**
- **PASS — conformance to accepted interval-less same-Stage association policy**
- **INCONCLUSIVE / NOT QUALIFIED — content-correct automatic turnover association**

Run 004 successfully exercised two human-realized Sessions on Stage `main`, preserved
all observed media, and produced the accepted conservative result when an ended
predecessor and active successor were both eligible for interval-less assets. It cannot
establish content-correct automatic turnover association because the actual substantive
Session B start is not durably known and the MP4 assets carry no trustworthy media
content intervals.

## Sanitized observed evidence

| Evidence | Observed result |
| --- | --- |
| Physical MP4 blocks | 49 |
| Durable Candidates | 49 |
| Registered Completed Media Assets | 49 |
| Session A automatic associations | 32 |
| Session B automatic associations | 0 |
| Unresolved associations | 17 |
| Conflicts | 0 |
| Stabilizing after final processing | 0 |
| Unresolved reason | all 17: `multiple_eligible_sessions` |
| Final Session A activity/package | `presentation_ended` / `assembling` |
| Final Session B activity/package | `presentation_ended` / `assembling` |
| Final Kernel health | ready, not recovering, reconciliation complete, no attention |

No asset was manually assigned and neither package was advanced.

## Session and boundary evidence

| Session | Durable authoritative start | Durable authoritative end |
| --- | --- | --- |
| A | `2026-08-11T17:53:22.092956-07:00` | `2026-08-11T18:21:39.497592-07:00` |
| B | `2026-08-11T18:24:56.370008-07:00` | `2026-08-11T18:39:17.585265-07:00` |

The operator reported that substantive Session B began before Codex completed the work
needed to invoke its StartSession command. Therefore B's durable authoritative start is
known to be later than the real substantive start. The exact real start is not present
in durable Run 004 evidence.

The controller passed literal `now` to the runner. The runner resolved it during
application-command preparation, after process start, lock/configuration/run-state work,
and immediately before the Kernel call. The B command was recorded as invoked at
`2026-08-12T01:24:56.141999+00:00`; the durable boundary was
`2026-08-12T01:24:56.370008+00:00`. This approximately 228-millisecond runner delta does
not include the earlier qualification-agent/operator-loop delay.

Qualification-agent latency must not be interpreted as production occurrence truth.
Later qualification runs capture the timestamp at controller entry, before guards and
runner startup, and pass that explicit aware value unchanged. A future product UI or
accepted inference must likewise preserve occurrence/acceptance time independently of
downstream processing and commit time.

## Association chronology and accepted-policy result

All 32 Session A association decisions occurred before B became durably authoritative.
All 17 unresolved decisions occurred afterward. The exact decision transition was:

- last A-associated asset registered at `18:23:21.455820-07:00` and was associated at
  `18:23:22.246048-07:00`;
- first unresolved asset was discovered at `18:23:10.830553-07:00`, carried a
  non-authoritative filesystem modification proxy 55.002 seconds before durable B start,
  registered at `18:25:32.492498-07:00`, and was then unresolved.

Filesystem modification times are proxies, not recorder-close or content-interval
truth. Of the 17 unresolved assets, proxy-only grouping places two within 60 seconds of
durable B start, two 60–180 seconds afterward, twelve later inside B's durable window,
and one approximately 5.6 seconds after B's durable end. Those groups do not establish
content membership.

The accepted Kernel predicate considers an interval-less asset compatible with an
active Session and with an ended Session whose package remains `assembling`. After B
started, A and B were therefore both eligible on the same Stage and the Kernel preserved
ambiguity as `multiple_eligible_sessions`. This is expected ADR-0024 behavior, not an
established implementation defect.

The durable A-end/B-start gap was 196.872 seconds. During it, 28 Candidates were first
discovered and 28 assets registered/associated with A. Because the actual B start could
have occurred after the last turnover cycle but before the B command, the evidence
supports only a range: 0–28 newly registered assets, or 0–33 distinct Candidates touched
by processing, may have been processed while B was substantively active but not yet
authoritative.

## Qualification procedure and telemetry findings

- Controller mutations did not overlap, Run-lock behavior remained clean, and no stale
  writer overwrote newer Run 004 evidence.
- No intentionally oversized batch was executed, but the turnover estimate used only 5
  durable Candidates while 27 additional physical files had accumulated. It estimated
  approximately 31.7 seconds; the observed batch took approximately 137.7 seconds.
- Qualification telemetry now uses the larger of durable observed media and a safe,
  bounded, shallow count of eligible configured source entries. It remains advisory and
  is not a production SLA.

## Interpretation boundary and deferred decision

Run 004 qualifies lifecycle execution, preservation, conservative ambiguity, and
conformance to the accepted interval-less policy. It does not qualify whether automatic
associations match the real A-to-B content boundary.

Changing predecessor eligibility when a same-Stage successor starts would alter accepted
Session/media-association semantics. That is a Yellow decision requiring explicit review
of trustworthy media timing, overlap handling, re-evaluation, and package consequences;
it is intentionally deferred.

## Post-run timing reconnaissance

A later read-only inspection found stable embedded UTC creation tags, zero-based stream
timestamps, and reproducible creation-time-plus-duration candidate intervals across all 49
retained media files. Run 004 lacks independent content-time ground truth, so those
intervals remain derived and unqualified; they do not revise this result or establish
content-correct association. See the sanitized
[vMix media timing evidence reconnaissance](../vmix-media-timing-reconnaissance.md) and
[calibration experiment](../vmix-media-timing-calibration.md).

## Preservation

Run 004's PostgreSQL database, 49 media files, external JSON/Markdown result, environment
metadata, configuration, and lock evidence remain outside Git and unchanged. This
sanitized result omits credentials, private absolute paths, filenames, corpus content,
and internal operation identifiers.
