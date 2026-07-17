# Completed Media Asset

ED-0048 defines the canonical deployment-neutral contract for one finalized logical
media asset that is safe for StageFlow to read. A finalized segment, complete recording,
clip, audio recording, or video recording may qualify independently. The entire
recording or Session does not need to be complete.

StageFlow observes recorded media; the production recording application owns recording,
codec and container selection, write behavior, segment creation, recovery, and physical
media creation. Production recording and livestream workloads always take priority.

## Contract boundary

A `CompletedMediaAsset` requires both an explicit finalized completion declaration and
categorical `safe_to_read` readiness. Completion, readiness, integrity, and technical
description are separate immutable contracts:

- completion says no more writes are expected for this individual asset;
- readiness says StageFlow may read without knowingly interfering with active writes;
- integrity describes declared checksum, probe, readability, and source-consistency
  facts where available;
- technical description retains optional probe-compatible media facts.

Completion and readiness both retain first-class limitations. ED-0049 uses completion
limitations for non-blocking gaps such as unavailable independent read or write-state
assessment; they are not hidden in metadata and do not collapse completion into
readiness.

The contract records those declarations. It does not detect file stability, assess
readiness, calculate checksums, probe containers, open files, watch directories, mount
storage, transfer media, queue work, or control recorders. An actively written or
unknown-readiness file cannot be a `CompletedMediaAsset`.

## Identity, resources, and time

Asset, manifest, primary-resource, declaration, Runtime, and provenance identities are
first-class `EntityId` references. Asset identity is not derived from filename, path,
mtime, checksum, sequence number, recorder, transfer destination, or deployment profile.
The manifest has an explicit schema name and version and must reference the same asset,
Runtime, primary resource, and related resources as the parent contract.

The primary resource retains an original filename, descriptive source location, size,
optional filesystem timestamps, media type, and container type without opening the
resource. Related sidecars remain lightweight ID references; ED-0048 does not define a
multi-file media package. Source paths are intentionally absent from
`CompletedMediaAssetSummary`.

Recording start/end, finalization, readiness assessment, integrity assessment,
manifest creation, and filesystem creation/modification timestamps remain distinct and
timezone-aware. Media timecode remains separate from wall-clock timestamps. Contracts
never read an implicit wall clock.

## Context and relationships

`CompletedMediaAssetContext` retains only explicitly supplied stage, recording-block,
scheduled-activity, correlation, recording-source, transcript-stream, and timeline
context. Scheduled activity is context, not Session identity. Filenames and paths are
descriptive and never establish authoritative Stage, recording-block, segment, asset,
or Session identity. No Session field exists.

Recording relationships may retain a recording group, parent, non-negative segment
index or sequence, previous/next asset references, expected and actual duration, and
first/final-known flags. Missing neighbors do not imply missing media. A final-known
segment does not prove Session completion, and segment numbering need not be contiguous
or fixed to sixty seconds. Complete recordings may exist without segments and may retain
related asset IDs without media assembly or reconciliation.

## Deployment neutrality

Software Agent, dedicated Node, external compatible source, and future Runtime profiles
produce the same contract and satisfy identical validation. Runtime profile, host,
recorder, adapter, producer, and source Event references are provenance only. Agent does
not mean lower trust; Node does not mean higher trust. Mixed deployment is supported,
packaging may differ, and shared Runtime semantics remain canonical. Borrowed compute is
preferred until dedicated hardware demonstrates evidence-backed operational value.

Optional capabilities may differ without creating first- and second-class assets. A
Node may provide detailed volume information while an Agent omits recorder version;
both remain valid when required identity, resource, completion, and readiness fields are
present. Deployment provenance never changes asset meaning, validation, lifecycle
priority, recording identity, Session identity, or Operational State keys.

## Determinism, serialization, and privacy

Contracts are frozen, slot-based, ID-oriented, and serialization-ready. Identifier and
string collections normalize to sorted unique tuples. Metadata is copied, recursively
frozen, restricted to serialization-friendly values, and rejects credential-shaped
keys. There are no callbacks, locks, streams, file descriptors, platform path objects,
media bytes, or mutable Runtime objects. Summaries deterministically sort warning codes
and omit sensitive source locations.

## Future boundaries

ED-0049 defines how supplied facts can justify that a candidate is finalized and safe
to read, without collecting those facts or constructing a full asset. It stops before
transfer or queueing, and future work should stop before transfer or queueing unless a
separate directive authorizes that boundary. A later asset-availability adapter may emit a
Production Event referencing the asset and manifest IDs:

```text
CompletedMediaAsset
-> future asset-availability Event adapter
-> Production Event
-> Observation
-> Evidence
```

ED-0048 does not create Production Events, Observations, Evidence, Operational State,
acceptance results, repository records, Runtime services, Agent or Node software,
transfer, ingest, queues, AI, APIs, workers, or frontend behavior. Completed media assets
are never stored in the Operational State Repository.
