# vMix media timing calibration experiment

## Status

**Proposed qualification experiment; not yet executed.** It is Green to run against an
isolated, non-customer corpus with the qualification probe. Its results cannot alone
accept the proposed production architecture or change association policy.

## Objective

Measure what vMix embedded `creation_time`, container duration, and stream packet timing
mean relative to an independent UTC reference and observable useful-content boundaries.
Separate repeatable recorder behavior from host/filesystem effects and quantify error,
drift, discontinuity, and restart behavior.

## Controlled setup

- Use an isolated workstation/configuration representative of the intended Event node.
- Record UTC, vMix version/build, recorder settings, segmentation length, codecs, frame
  rate, sample rate, host clock source/status, and local FFmpeg name/version.
- Feed a non-sensitive calibration source containing a millisecond UTC visual clock,
  monotonically numbered frames, and scheduled audio chirps from the same generator.
- Retain an independent generator log with aware UTC action times and monotonic sequence
  numbers. This is External recorder-test authority, not a StageFlow Session.
- Capture explicit recorder start/stop commands and vMix operational logs when available.
- Keep source media and raw logs outside Git; use safe aliases in sanitized reports.
- Run the qualification probe with explicit source, FFmpeg, safe alias, output paths, and
  a bound appropriate to the planned media count.

The generator clock must be independently checked against the host clock before and after
each trial. If the check is unavailable or either clock steps during a nominal-stability
trial, mark the trial invalid rather than estimating missing authority.

## Trial matrix

Run at least three repetitions per condition:

| Condition | Purpose |
| --- | --- |
| Normal start, three segment boundaries, normal stop | Baseline anchor, duration, cadence, finalization |
| Start and stop within five seconds of a segment boundary | Boundary behavior |
| Ten or more segments | Accumulated drift and cadence residuals |
| Recorder stop followed by restart | Sequence reset and anchor continuity |
| vMix process restart between recordings | Version/process lifecycle behavior |
| Host reboot between recordings | Filesystem and clock persistence effects |
| CPU/storage pressure within supported operating range | Finalization lag and timestamp stability |
| Intentional input discontinuity without host-clock change | Stream discontinuity behavior |

Clock-step, unsupported-overload, or fault-injection trials must be separately labeled;
they do not belong in the nominal profile sample.

## Measurements

For every segment, retain separately:

1. observed container tags, duration/start, stream descriptions, first/last packet PTS and
   DTS, file byte size, and filesystem proxy times;
2. external generator/log UTC for first and last identifiable content markers;
3. derived embedded-anchor candidate start/end and arithmetic adjacency residual;
4. calculated error of each candidate boundary against the external marker;
5. recorder-command-to-content and content-to-finalization latency where independently
   measurable;
6. tool, recorder configuration, host-clock, and trial-profile revisions.

Do not collapse missing markers into zero, interpolate across a clock step, or relabel a
filesystem timestamp as recorder close. Preserve raw values and exclusion reasons.

## Experiment-quality gates

A trial set is analyzable only when:

- all expected segment and generator sequence numbers are accounted for;
- all external timestamps are timezone-aware and traceable to the recorded clock check;
- source/config/tool revisions are complete;
- marker extraction is independently repeatable on a sample;
- exclusions and faults are explicit; and
- sanitized output contains no private paths, filenames, credentials, or content.

An analyzable result can establish a measured distribution for a named vMix/configuration
profile. It does not automatically make that profile acceptable for production. Product
and architecture must explicitly decide allowed error bounds, minimum repetitions,
expiry/requalification triggers, fault behavior, and authorized consumers.

## Expected artifacts

- external raw media and generator/recorder logs;
- immutable raw probe JSON plus its human-readable Markdown summary;
- a sanitized analysis containing per-condition sample count, median, maximum absolute
  error, percentile distribution, drift slope, discontinuities, exclusions, and failures;
- a proposed recorder-profile identifier/revision and exact configuration fingerprint;
- a recommendation to qualify, reject, or gather more evidence, clearly marked advisory.

## Stop conditions

Stop and preserve evidence if paths/content leak into a report, clock authority is lost,
the probe would overwrite an artifact, the recorder/config changes unexpectedly, or any
step would touch production/Event data. Do not compensate by changing Session or
association semantics.
