# Real-Event Playback Validation Result

## Result identity

- **Run ID:**
- **Run date:**
- **Operator:**
- **Mode:** Direct controlled media | vMix rolling replay
- **Outcome:** Passed | Passed with limitations | Failed | Aborted
- **Plan revision:** [Real-Event Playback Validation and UX Calibration](../plans/real-event-playback-validation.md)
- **Corpus ID / revision:**
- **Corpus item IDs:**
- **Event-day scenario links:**

## Evidence and handling declaration

- Footage use authorized: Yes | No
- Media remained outside Git: Yes | No
- Credentials/DSN omitted from this result: Yes | No
- Absolute private paths omitted: Yes | No
- Sensitive transcript/provider payload omitted: Yes | No | Not applicable
- External evidence retention location/reference:
- Limitations on sharing this result:

## Environment

- Host alias:
- OS/build:
- StageFlow revision:
- Python/uv versions:
- PostgreSQL version and deployment class:
- vMix version, if used:
- Clock synchronization method and measured offset:
- Network mode:
- Power/sleep posture observed (no settings changed by this run):

## Configuration summary

- Kernel configuration schema:
- Deployment ID:
- Business Event key:
- Stage/source binding keys:
- Source directory alias:
- Allowed extensions:
- Maximum candidates:
- Minimum stable seconds:
- Media-cycle interval and maximum cycle count:
- Event Mode / network policy:
- Configuration deviations:

Do not record the PostgreSQL DSN, secret value, or absolute media path.

## vMix replay configuration

- Input source stable ID/checksum:
- Playback rate:
- Recording format/container:
- Video codec/encoder mode:
- Resolution/frame rate:
- Audio codec/layout:
- Target segment duration:
- Actual segment-duration range:
- Filename pattern:
- Temporary/in-progress file behavior:
- Output close/finalization evidence:
- Other vMix settings affecting repeatability:

Use `Not applicable — direct mode` where appropriate.

## Human ground truth and commands

- Program Expectation recorded: Yes | No
- Program Expectation external identity/revision:
- Expected substantive start source offset:
- Expected substantive end source offset:
- Q&A included: Yes | No | Not applicable
- Authoritative Session start wall-clock time:
- Authoritative Session end wall-clock time:
- Stable bootstrap operation ID retained privately: Yes | No
- Stable Session command operation IDs retained privately: Yes | No
- Human assignment/correction performed:
- Package-ready action time:
- Package completion decision time/revision:

Operation IDs may be included only if the result's handling policy permits it. Never
include credentials.

## Cycle observations

| Cycle | Scope | Requested at | Duration | Candidates seen | Assets registered | Source failures | Notes |
| --- | --- | --- | --- | ---: | ---: | --- | --- |
|  |  |  |  |  |  |  |  |

## Per-block Kernel evidence

| Block alias | Close estimate / basis | First discovery | Safe to read | Registered | Association outcome | Session/package basis | Reasons/limitations |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |  |  |

## Current-Kernel measurements

| Measurement | Result | Method | Limitation |
| --- | --- | --- | --- |
| Discovery delay |  |  |  |
| Stabilization/readiness delay |  |  |  |
| Registration delay |  |  |  |
| Association coverage/outcomes |  |  |  |
| Presentation end to last relevant registration |  |  |  |
| Package-ready timing |  |  |  |
| Package completion timing |  |  |  |
| Restart reconstruction time |  |  |  |
| Reconciliation time/outcome |  |  |  |

Do not add transcription, Candidate, Editorial, render, or end-to-end intelligence
latency unless those capabilities existed and were explicitly part of a later run.

## Durable-state and restart verification

- Migrations `0001`–`0005` verified:
- Event/Stage IDs stable across restart:
- Session ID/revision stable across restart:
- Candidate/asset counts stable across restart:
- Ingress replay remained idempotent:
- Associations/history reconstructed:
- Package revision/completion history reconstructed:
- Fresh reconciliation completed before ready:
- PostgreSQL availability distinguished from reconciled readiness:
- Source files unchanged by StageFlow:
- Query/evidence references:

## UX calibration observations

- Blocks per Session:
- Normal block-close/arrival cadence:
- Peak simultaneous stabilizing/ready/registered counts:
- Turnover density:
- Ambiguous boundary-media frequency:
- Presentation end to last relevant block:
- Operator need for media-level detail:
- Default individual-block visibility recommendation:
- Mission Control noise hypothesis (future UI; not a current usability result):
- Event/Stage/Session context that must remain visible:
- Application-boundary start/end timing (not UI interaction timing):
- Producer-mark observations: Not applicable until implemented | Result
- Editorial observations: Not applicable until implemented | Result

## Scenario findings

For each linked Event-day scenario, record the tested invariant, evidence, result, and
untested portions. Do not mark the whole scenario passed from a partial run.

| Scenario | Invariant tested | Evidence | Result | Untested/limitation |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Future measurement placeholders

- Workflow latency: Not applicable until required capabilities exist | Result
- Transcription latency: Not applicable until implemented | Result
- Candidate latency/volume: Not applicable until implemented | Result
- Human-reference Moment overlap: Not applicable until implemented | Result
- Editorial queue/open/review latency: Not applicable until implemented | Result
- Editorial Clip availability: Not applicable until implemented | Result
- Assembly/render eligibility: Not applicable until implemented | Result
- Worker/vMix coexistence: Not qualified by ingest simulation | Separate result reference

## Deviations, failures, and preserved ambiguity

- Deviations from plan:
- Failed or aborted steps:
- Unresolved media:
- Conflicts:
- Human corrections:
- Preserved evidence/history:
- Suspected implementation defects requiring a separate task:

## Conclusion

- What this run established:
- What this run did not establish:
- Recommended single-variable next run:
- Production/Event readiness claimed: **No**
