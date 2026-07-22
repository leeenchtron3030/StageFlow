# Asset Stability and Readiness Detection

ED-0049 evaluates supplied objective resource-state observations deterministically. It
does not collect those observations. A future Runtime may discover a
candidate, collect facts, choose explicit parameters, and call the policy; this package
never watches directories, polls or sleeps, opens or reads media, inspects handles,
queries a recorder, probes containers, calculates checksums, transfers resources, or
enqueues work.

## Mission boundary

StageFlow is the fastest, most reliable observer of recorded event media for editorial
and session production. The production recording application owns recording, and
production recording and livestream workloads always take priority. The policy cannot
control production systems or interfere with an actively written resource.

A `MediaAssetCandidate` means only that StageFlow knows of a resource that may later
become eligible. It is not a completed asset and carries no final size, completion,
safe-readiness, transfer, queue, Session, semantic Observation, Evidence, or Operational
State claim. Filenames and paths are descriptive and never establish identity,
finalization, Stage context, or Session context.

## Policy semantics

`ConservativeAssetReadinessPolicy` is the one concrete ED-0049 policy. It consumes only
the immutable candidate, supplied observation bundle, explicit evaluation request, and
explicit immutable parameters. It reads no wall clock and has no mutable state.

The outcome precedence is:

1. invalid request
2. conflicting observation
3. unsupported source
4. explicit current blocker
5. successful strong-finalization route
6. successful stability-derived route
7. insufficient observation
8. unknown fallback

Strong finalization and stability-derived completion are distinct routes. A supported
recorder finalization, closed-segment notification, atomic rename, or sidecar marker can
qualify with post-finalization presence and no later contradiction. A source that lacks
an optional independent read or write-state capability can still use this route, with
the limitation preserved explicitly.

A stability-derived route requires a qualifying elapsed interval, continued presence,
successful non-destructive read access when configured, inactive write state under the
conservative parameters, no later change, and no replacement. Size stability alone does
not establish completion. A manual declaration has the same technical safeguards and
cannot override active writing, growth, absence, replacement, unreadability, or identity
conflict. The entire recording or Session does not need to be complete for one finalized
segment to qualify.

## Outputs and separation

Outcomes and reasons are categorical and explainable; readiness contains no score,
confidence, or probability. A safe evaluation supplies ED-0048-compatible
`CompletedMediaAssetCompletion` and `CompletedMediaAssetReadiness` declarations for a
later assembly boundary. ED-0049 does not construct, ingest, transfer, or publish a full
asset. Completion, safe-to-read readiness, and integrity remain separate facts.

Candidate, snapshot, finalization, write, read, presence, stability, evaluation, and
readiness timestamps remain semantically distinct and timezone-aware. Limitations are
first-class on observations, derived results, and declarations rather than being hidden
in metadata.

Agent, Node, external-compatible, Development, and genuinely unknown Runtime profiles
are peers. Development is first-class candidate provenance, not metadata and not a
trust tier. `unknown` is reserved for provenance that is unavailable or unresolved.
Agent does not mean lower trust; Node does not mean higher trust. Profile never selects
a more permissive rule or changes candidate, completion, readiness, or future asset
meaning. Unsupported capabilities are represented honestly instead of being invented.

These resource-state observations are not Production Events or the semantic production
`Observation` domain. The package does not create Production Events, Evidence, Runtime,
Agent, or Node services, APIs, workers, AI, or frontend behavior. Candidates,
observations, evaluations, and completed media assets are never stored in the
Operational State Repository. This boundary should stop before transfer or queueing.

## ED-0050 Runtime selection boundary

ED-0050 declares which source, observation, and readiness capabilities a Runtime says it
can support. Its readiness selection embeds this package's exact immutable policy
parameters, policy identity and version, required and optional capability IDs, selected
strong or stability route, and explicit fallback. Agent, Node, external-compatible,
Development, and unknown profiles use identical combination validation.

The Runtime selection is not an evaluation request or result. It does not collect an
observation bundle, derive a stability window, invoke `ConservativeAssetReadinessPolicy`,
or assert that any candidate is complete or safe to read. ED-0049 remains the sole
deterministic evaluation boundary over caller-supplied facts; ED-0050 remains declarative
configuration for a future executor.

## ED-0052 collection boundary

ED-0052 is that first bounded executor for discovery and fact collection, not for
readiness. Injected ports return `MediaAssetCandidate` values and the five objective
ED-0049 observation types. One explicit synchronous coordinator cycle deduplicates
candidates, retains identity conflicts, and may accumulate chronological observations
across cycles into an immutable `AssetReadinessObservationBundle`.

Collection does not interpret latest state, derive a stability window, invoke
`ConservativeAssetReadinessPolicy`, produce completion/readiness declarations, or
construct an ED-0048 asset. Agent permission and explicit budgets can defer or
interrupt collection without discarding facts already supplied. No filesystem or
recorder collector is implemented by ED-0052; future Agent and Node adapters supply the
same ports.

## ED-0053 candidate boundary

ED-0053 supplies only the first step: eligible regular filesystem entries become
immutable `MediaAssetCandidate` values. Stable object identity is preferred; a
location-scoped fallback carries explicit limitations. Extension-derived media,
container, or asset-kind values remain hints, while Stage and recording-block context
comes only from the configured ED-0050 target.

The candidate's Runtime profile is canonical first-class provenance. A Development
Runtime produces `runtime_profile = development`; downstream consumers never need
metadata to recover it. Profile remains excluded from resource, candidate, and proposed
asset identity seeds and does not affect eligibility, ordering, or readiness meaning.

The adapter intentionally omits final size, filesystem modification time, checksums,
duration, content probes, write/read/finalization facts, stability windows, completion,
and readiness. Active and zero-byte files may be candidates. Future ED-0054 snapshot
observation must remain a separate one-shot objective fact supplier; ED-0049 remains the
only readiness evaluation boundary.
