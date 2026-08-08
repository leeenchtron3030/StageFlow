# Segment and media lifecycle

This document uses “segment” as a workflow concept while the canonical durable record
name remains open. It distinguishes current ED-0048–0053 contracts from the accepted
future media path.

## Current implementation

### Discovery

The local filesystem adapter performs one explicit synchronous stateless call for one
configured local-file or mounted-volume target. It is read-only, shallow, bounded,
deterministically ordered, and does not watch, poll, recurse, follow known symlinks, open
media content, transfer, or delete. It returns Media Asset Candidates and typed
limitations/errors.

The accepted filesystem race finding is hardened with descriptor-bound enumeration and
child inspection on POSIX platforms where Python exposes descriptor `scandir` and
no-follow directory-open flags. Windows and other unsupported platforms use pre/post
target identity revalidation around enumeration and child inspection. Persistent
missing, inaccessible, symlinked, non-directory, or identity-changed targets fail closed
without candidates. The fallback cannot detect a transient swap-and-restore entirely
between checkpoints, and filesystems without meaningful device/object identifiers can
only revalidate target type and symlink status. Deployments must not claim stronger
replacement detection. Discovery still grants no authority to later content access,
which must independently revalidate both identity and permission.

### Identity and candidate state

A Media Asset Candidate carries deterministic candidate, resource, and proposed-asset
identity derived from authoritative Runtime/source/resource facts. Deployment profile is
provenance and does not create an identity or trust tier. Candidate has no lifecycle
status enum; discovery only establishes that a resource is eligible for observation.

The collection coordinator deduplicates candidate IDs and operation replays within one
process. Its maps, history, conflicts, and observation bundles disappear on restart.

### Resource observation and readiness

The coordinator accepts injected objective resource-observation ports, but no concrete
snapshot observer or repeated-observation scheduler is implemented. The readiness policy
evaluates caller-supplied facts with outcomes:

- `safe_to_read`
- `not_safe_to_read`
- `insufficient_observation`
- `conflicting_observation`
- `unsupported_source`
- `invalid_request`
- `unknown`

Discovery never chooses one of these outcomes. A visible, active, or zero-byte file may
be a valid candidate while remaining not ready.

### Completed asset

`CompletedMediaAsset` is an immutable validation contract. It requires finalized
completion and categorical `safe_to_read` readiness plus consistent manifest, resource,
source, provenance, context, and timestamps. No current assembler, registry, repository,
or application workflow creates and persists one from discovery results.

### Processing and Session relationship

No current component registers a durable segment, emits an asset-registration Production
Event, assigns a Completed Media Asset to a Session, creates a Job, transcribes, analyzes,
renders, retries, or reconciles after restart.

## Accepted target flow

ADR-0020 records the accepted order:

```mermaid
flowchart LR
    Discover[Discover Media Asset Candidate] --> Persist[Persist candidate identity and provenance]
    Persist --> Observe[Record objective Media Resource Observations]
    Observe --> Ready[Evaluate readiness]
    Ready --> Assemble[Assemble immutable Completed Media Asset]
    Assemble --> Register[Register in durable media registry]
    Register --> Event[Emit stable asset-registration Production Event]
    Event --> Associate[Associate with authoritative Session]
    Associate --> Work[Schedule approved durable operations]
```

Incomplete or merely discovered files must not be represented as completed-segment
Events. Each step remains independently testable; the sequence must not be collapsed into
one stateful watcher-manager.

## Lifecycle definitions

| Milestone | Meaning | Current status |
| --- | --- | --- |
| Candidate discovered | An explicitly authorized source resource is eligible for observation | Implemented in one-shot local adapter |
| Candidate persisted | Stable identity/provenance is durable and uniquely registered | Accepted future; not implemented |
| Resource observed | One immutable objective resource snapshot/fact is recorded | Contract/port only |
| Readiness evaluated | Explicit policy evaluates an ordered fact bundle | Policy implemented; execution/persistence absent |
| Completed asset assembled | Finalized, safe-to-read facts satisfy the immutable asset contract | Contract only |
| Asset registered | Completed asset and manifest are durably committed | Accepted future; not implemented |
| Registration Event emitted | Stable Production Event records asset availability | Accepted in ADR-0020; not implemented |
| Session associated | Explicit authority links registered asset to a Session or review queue | Accepted future; policy open |
| Downstream work scheduled | Durable operation records approved processing | Accepted future; not implemented |

These are milestone definitions, not approved database enum names.

## Duplicate, rename, ordering, and reconciliation

- Equivalent authoritative source facts must reproduce equivalent resource, candidate,
  and proposed-asset identity.
- Duplicate notifications and collection calls must not create duplicate durable records
  or effects.
- Stable source identity and trustworthy source event identity are preferred; otherwise
  use a versioned canonical fingerprint of authoritative facts.
- Mutable metadata never participates in authoritative identity.
- Current identity includes normalized location; rename continuity, aliasing, and
  same-object/different-path reconciliation remain open.
- Arrival order is not assumed to be timeline or Session order. Future registration must
  preserve source sequence/times when known and tolerate out-of-order facts.
- A changed directory object during enumeration must cause rejection rather than return
  candidates from an unchecked object.

## Failure, retry, and recovery

- Deterministic discovery/readiness/assembly decisions remain synchronous.
- Asynchronous processing or external work uses future database-backed durable operations
  with stable identity, claim/lease, attempts, bounded retry, retryability, offline
  deferral, idempotent result commit, and operator-visible status.
- Process or machine restart must reconstruct candidate registration, observations,
  readiness/asset records, operation attempts, and Session association from durable
  state, then reconcile explicitly configured sources.
- Source files may remain after state loss, but filenames/directories alone are not a
  durable registry.
- Provider or Internet failure must not stop the local event-critical path.

No durable Job/Operation implementation exists yet; the exact schema and worker lifecycle
require a plan and, where architectural choices remain, an ADR.

## Late and out-of-order media

Late media must enter the same candidate-to-registration path and must not silently mutate
a final or published Session revision. Association may require an explicit reopening,
new reviewable revision, or quarantine outcome. Grace duration and automated versus
operator-approved behavior remain open in the Session lifecycle decision.

## Required invariants

1. Discovery is not readiness, and readiness is not registration.
2. A Completed Media Asset is finalized and categorically safe to read.
3. Media content remains outside the relational database and is referenced by durable
   records.
4. Candidate/resource/asset identity is deterministic from authoritative facts and is
   independent of deployment profile labels.
5. Agent, Node, Development, external-compatible, and unknown profiles are provenance,
   not trust or identity tiers.
6. All external/persisted times are aware; source, observation, readiness, finalization,
   registration, and commit meanings remain distinct.
7. Duplicate delivery and restart are handled by durable identity and idempotent commits,
   not process memory.
8. Session association is explicit and does not arise from a directory name.
9. Later content access independently revalidates authority and identity.
10. Network-dependent processing is visible and deferrable where approved.

## Open questions

- Canonical name and schema for the durable Source Segment/media record.
- Rename/alias and multi-mount identity reconciliation.
- Concrete snapshot-observation ownership and sampling policy.
- Initial media registry transaction boundaries and uniqueness constraints.
- Session association/review-queue authority.
- Grace duration and late-media reopening/quarantine policy.
- Database, migrations, backup/restore, and worker deployment details.
