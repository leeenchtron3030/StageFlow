# StageFlow Runtime

ED-0050 defines one deployment-neutral Runtime contract for every StageFlow deployment.
An Agent on a production workstation, a dedicated Node, an external-compatible peer,
and a development installation use the same immutable `StageFlowRuntime` graph. Agent
does not mean lower trust; Node does not mean higher trust. A profile describes
packaging and placement, never semantic authority, readiness confidence, or priority.

The Runtime is a declarative technical boundary. It says which identity, version, host,
configuration, capabilities, source scopes, collection plans, readiness routes,
resource constraints, event-mode expectations, assembly mappings, limitations, health,
and availability have been explicitly supplied. It is not a service, daemon, process,
worker, repository, or singleton. Multiple Runtime values with distinct Runtime IDs can
coexist without shared state.

## Mission and production priority

StageFlow observes recorded event media so that editorial and session-production work
can begin quickly and reliably. The production recording application owns recording,
media creation, write behavior, recovery, and physical storage. Production recording
and livestream workloads always take priority over StageFlow.

Event configurations therefore declare a `production_subordinate` resource policy,
non-writing source observation, reducible or suspendable optional work, constrained GPU
use, preservation of source ownership, and a response for normal, elevated, critical,
and recording-safety-uncertain pressure. These are future behavior requirements, not
measurements or enforcement. Resource budgets are optional limits; their absence means
unspecified, not unlimited.

The contract supports offline-capable event operation. Internet access is never a
condition for event candidate readiness. Network declarations distinguish offline,
local-network-only, optional-network, required-network, and disabled configurations;
`network_required` is invalid for event mode.

## Identity, configuration, and time

`RuntimeIdentity` gives the Runtime a first-class ID, logical name, profile, host,
installation, organization, event deployment, and configured Stage references.
Hostname is descriptive and cannot substitute for Runtime identity. There is no Session
identity. Scheduled activity and recording-block references remain explicit context and
never create a Session aggregate.

`RuntimeVersion` declares semantic, contract-compatibility, configuration-schema, and
capability-schema versions plus optional build identity and caller-supplied build time.
`RuntimeHost` is a supplied description, not hardware discovery or benchmarking.
`RuntimeConfiguration` is an immutable versioned graph. Reconfiguration creates a new
value; the package does not mutate an installed process or persist settings.

Build, capability-declaration, configuration, health-assessment, availability, event
window, and limitation times remain distinct and timezone-aware. The package reads no
implicit wall clock.

## Capabilities and collection declarations

General capabilities use categorical `supported`, `unsupported`, `degraded`, or
`unknown` status. Degraded support requires a first-class limitation. Source,
observation, and readiness capability contracts specialize the general declarations by
ID without hiding support in metadata. Conflicting duplicate IDs and incompatible
kind/scope declarations are invalid; exact duplicates normalize deterministically.

Source capabilities declare local-file, mounted-volume, network-share,
external-reference, or unknown schemes; host and volume scope; read access mode;
adapter identity; and recorder-application compatibility. Collection targets retain an
opaque location reference and explicit context. Credential-bearing references are
rejected. A location is descriptive and does not prove existence, ownership,
completion, readiness, Stage context, or Session context.

Observation capabilities map only to the ED-0049 resource facts: snapshot,
finalization, write state, read access, and resource presence. A collection plan names
targets, selected observation capabilities, supplied collection modes, readiness
selection, resource policy, and event mode. It does not collect observations. There is
no watcher, polling loop, filesystem reader, recorder query, handle inspection, probe,
or scheduler.

## Readiness and asset assembly boundaries

`RuntimeReadinessPolicySelection` embeds the exact immutable ED-0049 policy parameters,
policy identity and version, required and optional capability IDs, selected route, and
fallback. Strong-finalization and stability-derived routes remain distinct. A stability
route requires snapshot, presence, stable identity, and any read/write capabilities
required by its explicit parameters. A strong route requires an accepted finalization
method and post-finalization presence when configured. Capability combinations are
validated identically for all profiles.

The package does not evaluate candidate readiness. It selects a future policy route but
creates no candidate, observation bundle, stability window, evaluation, completion, or
safe-to-read result.

`RuntimeAssetAssemblyPlan` declares how a future boundary could map explicit Runtime,
recorder, or adapter context into the ED-0048 manifest vocabulary. Filename-only and
path-only context remain non-authoritative limitations. Source-location handling and
summary privacy are explicit. The package does not assemble completed media assets,
calculate checksums, probe media, open sources, or create manifests.

## Health, availability, and validation

Health, availability, and configuration validity are separate declarations:

- validation asks whether the supplied graph is internally coherent;
- health describes currently declared capability and policy condition;
- availability describes whether the Runtime is declared available for StageFlow work.

A healthy Runtime can be unavailable because its mode is disabled, or limited in
maintenance mode. A degraded Runtime can remain available with non-blocking
limitations. An unhealthy Runtime cannot claim available event work. No active health
check, liveness monitor, pressure measurement, or capability probe exists.

`validate_runtime()` is a pure deterministic combination validator. It checks identity,
schema, capability conflicts and references, event/resource compatibility, target and
observation support, readiness and fallback feasibility, ED-0048 assembly compatibility,
limitation references, health, and availability. Invalid declarations take precedence;
then valid with limitations, valid, and explicit unknown handling. Input ordering does
not alter result or reason ordering.

Configuration validity does not mean execution success. A valid graph says only that
the declared contracts could support the configured responsibilities. It does not say
that a process is running, a source exists, an adapter is connected, a recorder is
healthy, a candidate is complete, an asset was assembled, or downstream work succeeded.

## Explicit non-goals

ED-0050 does not control a recorder. It does not create Production Events or semantic
Observations, Evidence, Operational State, repository records, or Sessions. It does not
collect observations, evaluate candidate readiness, assemble completed media assets,
transfer or queue assets, persist configuration, access a network, expose an API, run a
worker, call AI, or add frontend behavior. Deployment and process lifecycle belong to a
future directive.

In particular, the Runtime contract does not transfer or queue assets.

## ED-0051 execution relationship

ED-0051 adds the first executable profile as a separate `SoftwareAgentRuntime`
lifecycle. The ED-0050 aggregate remains immutable and deployment-neutral; the Agent
adapter validates it and then treats its embedded `RuntimeConfiguration` as
authoritative. Construction performs no work and startup is explicit. Supplied
production pressure controls lifecycle permission conservatively, with uncertainty
suspending event-mode work until explicit resume. The lifecycle adds no media access,
readiness execution, asset assembly, transfer, persistence, service, or Node adapter.

## ED-0052 collection relationship

ED-0052 consumes the validated embedded configuration rather than changing it. One
explicit synchronous cycle resolves a configured collection plan, target, discovery
capability, observation capabilities, readiness selection, event mode, and resource
policy. The Runtime remains declarative: injected ports supply all candidate and
objective observation facts, while ED-0051 permission gates each bounded call.

Required capability IDs receive priority over optional IDs; reduced permission defers
optional collection. Candidate and observation facts accumulate process-locally, but
no readiness route is evaluated and no assembly plan is executed. ED-0052 adds no
filesystem or recorder adapter, scheduler, persistence, transfer, queue, network, or
service. Agent and a future Node use the same Runtime meanings and media port contracts.
