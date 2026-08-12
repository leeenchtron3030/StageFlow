export type AttentionLevel = "information" | "review" | "intervention";
export type HealthState = "ready" | "degraded" | "unavailable" | "unknown";
export type DataSourceKind = "fixture" | "kernel";
export type DataSourceState =
  | "development_fixture"
  | "live_connected"
  | "live_unavailable"
  | "live_unconfigured";

export interface DataSourceView {
  kind: DataSourceKind;
  label: string;
  state: DataSourceState;
  statusLabel: string;
  scenarioId?: string;
  scenarioLabel?: string;
  updatedAt: string;
  authoritative: boolean;
}

export interface AttentionItemView {
  id: string;
  level: AttentionLevel;
  title: string;
  scope: string;
  since: string;
  impact: string;
  safeContinuation: string;
  action: string;
}

export interface MediaSummaryView {
  discovered: number;
  stabilizing: number;
  registered: number;
  associated: number;
  unresolved: number;
  conflicting: number;
  lastActivityAt?: string;
}

export interface MediaAssetView {
  candidateId: string;
  assetId?: string;
  stageId: string;
  stageKey: string;
  stageName: string;
  sourceBindingKey: string;
  registrationState: "discovered" | "stabilizing" | "ready" | "registered" | "unknown";
  associationStatus: "associated" | "unresolved" | "conflict" | "not_evaluated";
  associationAuthority?: "deterministic" | "human";
  sessionId?: string;
  consideredSessionIds: string[];
  discoveredAt: string;
  lastObservedAt: string;
  candidateStartedAt?: string;
  candidateEndedAt?: string;
  epistemicKinds: string[];
  diagnosticCodes: string[];
  associationReasonCodes: string[];
  associationPolicy?: string;
  explanation: string;
  boundedProjection: true;
}

export interface SessionView {
  id: string;
  title: string;
  stageKey: string;
  stageName: string;
  expectationTitle?: string;
  activityState: "expected" | "presentation_active" | "presentation_ended";
  packageState:
    | "assembling"
    | "ready_for_review"
    | "in_review"
    | "correction_required"
    | "complete";
  packageRevision: number;
  sessionRevision: number;
  authoritativeStart?: string;
  authoritativeEnd?: string;
  media: MediaSummaryView;
  attentionLevel?: AttentionLevel;
  attentionText?: string;
  completedAt?: string;
  provenance: "declared" | "external" | "fixture";
}

export interface StageView {
  id: string;
  key: string;
  name: string;
  sourceState: HealthState;
  sourceLabel: string;
  sourceImpact: string;
  currentSession?: SessionView;
  previousSession?: SessionView;
  nextExpectation?: string;
  media: MediaSummaryView;
  attentionLevel?: AttentionLevel;
  attentionText?: string;
}

export interface InfrastructureItemView {
  id: string;
  label: string;
  health: HealthState;
  state: string;
  impact: string;
  attentionLevel?: AttentionLevel;
  detail?: string;
}

export interface EditorialCandidateView {
  id: string;
  sessionId: string;
  sessionTitle: string;
  stageName: string;
  at: string;
  origin: "machine" | "producer" | "editorial";
  state: "candidate" | "priority" | "approved" | "deferred";
  excerpt: string;
  reason: string;
}

export interface MediaTimingEvidenceView {
  evidenceId: string;
  assetId: string;
  stageKey: string;
  sessionId?: string;
  revision: number;
  providerLabel: string;
  toolLabel: string;
  inspectedAt?: string;
  observations: Array<{
    kind: string;
    precision?: string;
    limitations: string[];
  }>;
  derivationIdentity?: string;
  candidateStartedAt?: string;
  candidateEndedAt?: string;
  evidenceLabel: string;
  derivationLabel?: string;
  qualificationStatus: "unqualified" | "qualified" | "rejected" | "expired";
  recorderProfileLabel: string;
  precision?: string;
  limitations: string[];
  authorizedUse: "advisory_only";
}

export interface EventView {
  id?: string;
  key: string;
  name: string;
  lifecycle: "setup" | "armed" | "active" | "closing" | "post_event";
  modeLabel: string;
  ready: boolean;
  recovering: boolean;
  databaseAvailable: boolean;
  stageCount: number;
}

export interface OperationalWorkspace {
  dataSource: DataSourceView;
  event: EventView;
  stages: StageView[];
  sessions: SessionView[];
  mediaAssets: MediaAssetView[];
  attention: AttentionItemView[];
  infrastructure: InfrastructureItemView[];
  editorialCandidates: EditorialCandidateView[];
  editorialClips: Array<{
    id: string;
    sessionId: string;
    sessionTitle: string;
    rangeLabel: string;
    reviewLabel: string;
    simulated: true;
  }>;
  transcriptState: {
    state: "not_connected" | "fixture_available" | "deferred";
    label: string;
    detail: string;
  };
  mediaTimingEvidence: MediaTimingEvidenceView[];
  mediaTimingEvidenceStatus: "not_requested" | "available" | "unavailable";
}

export interface ScenarioOption {
  id: string;
  label: string;
  group: "operational" | "evidence";
}
