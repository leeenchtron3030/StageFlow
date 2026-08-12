import type {
  AttentionItemView,
  AttentionLevel,
  InfrastructureItemView,
  MediaSummaryView,
  MediaTimingEvidenceView,
  OperationalWorkspace,
  SessionView,
  StageView,
} from "./model.ts";

export interface KernelSessionStatus {
  session_id: string;
  activity_state: string;
  package_state: string;
  package_revision: number;
  revision: number;
  authoritative_start: string;
  authoritative_end: string | null;
  program_expectation_title: string | null;
}

export interface KernelStageStatus {
  stage_id: string;
  key: string;
  name: string;
  source_available: boolean | null;
  session_id: string | null;
  assembling_sessions: KernelSessionStatus[];
  recent_sessions: KernelSessionStatus[];
  session_activity_state: string | null;
  session_package_state: string | null;
  session_package_revision: number | null;
  session_revision: number | null;
  session_authoritative_start: string | null;
  session_authoritative_end: string | null;
  last_media_arrived_at: string | null;
  discovered: number;
  stabilizing: number;
  ready: number;
  registered: number;
  associated: number;
  unresolved: number;
  conflicting: number;
  attention_codes: string[];
}

export interface KernelStatusPayload {
  configured: boolean;
  configuration_supplied: boolean;
  configuration_valid: boolean | null;
  runtime_composed: boolean;
  event_id: string | null;
  event_key: string | null;
  event_name: string | null;
  database_available: boolean;
  ready: boolean;
  recovering: boolean;
  reconciliation_status: string | null;
  reconciliation_started_at: string | null;
  reconciliation_completed_at: string | null;
  stages: KernelStageStatus[];
  recent_media?: KernelMediaStatus[];
  attention_codes: string[];
  startup_error?: string | null;
}

export interface KernelMediaStatus {
  asset_id: string | null;
  stage_id: string;
  session_id: string | null;
}

export interface KernelMediaTimingEvidenceHistory {
  asset_id: string;
  active_revision: number | null;
  evidence: Array<{
    evidence_id: string;
    revision: number;
    provider_id: string;
    provider_version: string;
    tool_id: string;
    tool_version: string;
    recorder_profile_id: string;
    recorder_profile_revision: number;
    qualification_status: "unqualified" | "qualified" | "rejected" | "expired";
    qualification_limitations: string[];
    observations: Array<{
      epistemic_kind: string;
      kind: string;
      precision: string | null;
      limitations: string[];
    }>;
    derivations: Array<{
      epistemic_kind: string;
      rule_id: string;
      rule_version: string;
      candidate_started_at: string;
      candidate_ended_at: string;
      limitations: string[];
    }>;
    limitations: string[];
    authorized_use: "advisory_only";
  }>;
}

export function adaptKernelMediaTimingEvidence(
  payload: KernelMediaTimingEvidenceHistory,
  media: KernelMediaStatus,
  stages: KernelStageStatus[],
): MediaTimingEvidenceView[] {
  const stageKey = stages.find((stage) => stage.stage_id === media.stage_id)?.key;
  if (!stageKey) return [];
  return payload.evidence.map((evidence) => {
    const derivation = evidence.derivations[0];
    const precision = evidence.observations
      .map((observation) => observation.precision)
      .filter((value): value is string => Boolean(value))
      .join(", ");
    return {
      evidenceId: evidence.evidence_id,
      assetId: payload.asset_id,
      stageKey,
      sessionId: media.session_id ?? undefined,
      revision: evidence.revision,
      candidateStartedAt: derivation?.candidate_started_at,
      candidateEndedAt: derivation?.candidate_ended_at,
      evidenceLabel: `${evidence.provider_id} ${evidence.provider_version} · ${evidence.tool_id} ${evidence.tool_version}`,
      derivationLabel: derivation
        ? `${derivation.rule_id} · rule ${derivation.rule_version}`
        : undefined,
      qualificationStatus: evidence.qualification_status,
      recorderProfileLabel: `${evidence.recorder_profile_id} · revision ${evidence.recorder_profile_revision}`,
      precision: precision || undefined,
      limitations: [
        ...evidence.qualification_limitations,
        ...evidence.limitations,
        ...(derivation?.limitations ?? []),
      ],
      authorizedUse: evidence.authorized_use,
    };
  });
}

function mediaFromStage(stage: KernelStageStatus): MediaSummaryView {
  return {
    discovered: stage.discovered,
    stabilizing: stage.stabilizing,
    registered: stage.registered,
    associated: stage.associated,
    unresolved: stage.unresolved,
    conflicting: stage.conflicting,
    lastActivityAt: stage.last_media_arrived_at ?? undefined,
  };
}

function activityState(value: string): SessionView["activityState"] {
  if (value === "presentation_ended") return "presentation_ended";
  if (value === "presentation_active") return "presentation_active";
  return "expected";
}

function packageState(value: string): SessionView["packageState"] {
  if (value === "ready_for_review") return "ready_for_review";
  if (value === "in_review") return "in_review";
  if (value === "correction_required") return "correction_required";
  if (value === "complete") return "complete";
  return "assembling";
}

function sessionFromProjection(
  projection: KernelSessionStatus,
  stage: KernelStageStatus,
): SessionView {
  return {
    id: projection.session_id,
    title:
      projection.program_expectation_title ??
      `Session ${projection.session_id.slice(0, 8)}`,
    stageKey: stage.key,
    stageName: stage.name,
    expectationTitle: projection.program_expectation_title ?? undefined,
    activityState: activityState(projection.activity_state),
    packageState: packageState(projection.package_state),
    packageRevision: projection.package_revision,
    sessionRevision: projection.revision,
    authoritativeStart: projection.authoritative_start,
    authoritativeEnd: projection.authoritative_end ?? undefined,
    media: mediaFromStage(stage),
    attentionLevel:
      stage.unresolved > 0 || stage.conflicting > 0 ? "review" : undefined,
    attentionText:
      stage.conflicting > 0
        ? `${stage.conflicting} conflicting media`
        : stage.unresolved > 0
          ? `${stage.unresolved} unresolved media`
          : undefined,
    provenance: "declared",
  };
}

function currentSessionFromStage(stage: KernelStageStatus): SessionView | undefined {
  const projection = [...stage.assembling_sessions, ...stage.recent_sessions].find(
    (item) => item.session_id === stage.session_id,
  );
  if (projection) return sessionFromProjection(projection, stage);
  if (!stage.session_id || !stage.session_activity_state || !stage.session_package_state) {
    return undefined;
  }
  return {
    id: stage.session_id,
    title: `Session ${stage.session_id.slice(0, 8)}`,
    stageKey: stage.key,
    stageName: stage.name,
    activityState: activityState(stage.session_activity_state),
    packageState: packageState(stage.session_package_state),
    packageRevision: stage.session_package_revision ?? 1,
    sessionRevision: stage.session_revision ?? 1,
    authoritativeStart: stage.session_authoritative_start ?? undefined,
    authoritativeEnd: stage.session_authoritative_end ?? undefined,
    media: mediaFromStage(stage),
    provenance: "declared",
  };
}

function stageAttention(stage: KernelStageStatus): {
  level?: AttentionLevel;
  text?: string;
} {
  if (stage.source_available === false) {
    return { level: "intervention", text: "Configured source unavailable" };
  }
  if (stage.conflicting > 0) {
    return { level: "review", text: `${stage.conflicting} association conflicts` };
  }
  if (stage.unresolved > 0) {
    return { level: "review", text: `${stage.unresolved} unresolved media` };
  }
  return {};
}

function stageView(stage: KernelStageStatus): StageView {
  const current = currentSessionFromStage(stage);
  const priorProjection = [...stage.assembling_sessions, ...stage.recent_sessions].find(
    (item) => item.session_id !== stage.session_id,
  );
  const state = stageAttention(stage);
  return {
    id: stage.stage_id,
    key: stage.key,
    name: stage.name,
    sourceState:
      stage.source_available === true
        ? "ready"
        : stage.source_available === false
          ? "unavailable"
          : "unknown",
    sourceLabel:
      stage.source_available === true
        ? "Available"
        : stage.source_available === false
          ? "Unavailable"
          : "Not reported",
    sourceImpact:
      stage.source_available === false
        ? "New media cannot currently be observed from this configured source."
        : "Local media observation state reported by the Kernel.",
    currentSession: current,
    previousSession: priorProjection
      ? sessionFromProjection(priorProjection, stage)
      : undefined,
    media: mediaFromStage(stage),
    attentionLevel: state.level,
    attentionText: state.text,
  };
}

function stageAttentionItem(stage: StageView): AttentionItemView | undefined {
  if (!stage.attentionLevel) return undefined;
  if (stage.sourceState === "unavailable") {
    return {
      id: `${stage.id}-source-unavailable`,
      level: "intervention",
      title: "Configured source unavailable",
      scope: stage.name,
      since: "Current status",
      impact: "StageFlow cannot observe new media from this source.",
      safeContinuation: "Existing durable media and Session authority remain preserved.",
      action: "Verify the configured source before relying on new ingestion.",
    };
  }
  return {
    id: `${stage.id}-media-review`,
    level: "review",
    title: "Media association requires review",
    scope: stage.name,
    since: "Current status",
    impact: stage.attentionText ?? "Media ownership is uncertain.",
    safeContinuation: "Media is preserved. StageFlow has not guessed ownership.",
    action: "Review when authoritative evidence is available.",
  };
}

function globalAttention(payload: KernelStatusPayload): AttentionItemView[] {
  if (!payload.configuration_supplied) {
    return [
      {
        id: "kernel-not-configured",
        level: "information",
        title: "Kernel not configured",
        scope: "Local backend",
        since: "Current status",
        impact: "No Event or Stage projection is loaded in this backend process.",
        safeContinuation: "The frontend remains available for read-only setup inspection.",
        action: "Supply a validated Kernel configuration and explicitly bootstrap the Event.",
      },
    ];
  }
  if (payload.configuration_valid === false) {
    return [
      {
        id: "kernel-configuration-invalid",
        level: "review",
        title: "Kernel configuration invalid",
        scope: "Local backend",
        since: "Current status",
        impact: "No Event authority can be composed from the supplied configuration.",
        safeContinuation: "No existing Event state is being represented by this process.",
        action: "Correct and revalidate the supplied Kernel configuration.",
      },
    ];
  }
  if (!payload.database_available) {
    return [
      {
        id: "postgresql-unavailable",
        level: "intervention",
        title: "Authoritative control unavailable",
        scope: "Event",
        since: "Current status",
        impact: "Session and package authority cannot be read or changed.",
        safeContinuation: "Primary recording may continue independently; status is stale.",
        action: "Restore PostgreSQL and complete fresh reconciliation.",
      },
    ];
  }
  if (payload.recovering || !payload.ready) {
    return [
      {
        id: "kernel-not-ready",
        level: payload.recovering ? "review" : "information",
        title: payload.recovering ? "Authoritative state recovering" : "Kernel not ready",
        scope: "Event",
        since: "Current status",
        impact: "Fresh reconciled Event state is not yet available.",
        safeContinuation: "The interface remains read-only and preserves the last context.",
        action: payload.recovering
          ? "Wait for reconciliation before authority actions."
          : "Complete Kernel configuration and bootstrap.",
      },
    ];
  }
  return [];
}

function infrastructure(payload: KernelStatusPayload): InfrastructureItemView[] {
  const sourceCount = payload.stages.filter((stage) => stage.source_available === true).length;
  const configurationReady = payload.configuration_supplied && payload.configuration_valid === true;
  return [
    {
      id: "postgresql",
      label: "PostgreSQL",
      health: !configurationReady
        ? "unknown"
        : payload.database_available
          ? "ready"
          : "unavailable",
      state: !configurationReady
        ? "Not configured"
        : payload.database_available
          ? "Available"
          : "Unavailable",
      impact: !configurationReady
        ? "Database availability is not evaluated until Kernel configuration is valid."
        : payload.database_available
          ? "Authoritative durable state is reachable."
          : "Authoritative actions paused; recording may continue independently.",
      attentionLevel:
        configurationReady && !payload.database_available ? "intervention" : undefined,
    },
    {
      id: "reconciliation",
      label: "Reconciliation",
      health: payload.ready ? "ready" : payload.recovering ? "degraded" : "unknown",
      state: payload.recovering
        ? "Recovering"
        : payload.reconciliation_status ?? "Not completed",
      impact: payload.ready
        ? "Kernel status is fresh and reconciled."
        : "Authority remains read-only until fresh reconciliation succeeds.",
      attentionLevel: payload.recovering ? "review" : undefined,
      detail: payload.reconciliation_completed_at
        ? `Completed ${payload.reconciliation_completed_at}`
        : undefined,
    },
    {
      id: "sources",
      label: "Stage sources",
      health:
        payload.stages.length === 0
          ? "unknown"
          : sourceCount === payload.stages.length
            ? "ready"
            : "degraded",
      state: `${sourceCount} / ${payload.stages.length} available`,
      impact: "Availability describes observation reachability, not recorder truth.",
    },
    {
      id: "workers",
      label: "Intelligence workers",
      health: "unknown",
      state: "Not implemented",
      impact: "No transcription or Moment execution is part of the current Kernel.",
    },
    {
      id: "internet",
      label: "Internet",
      health: "unknown",
      state: "Not reported",
      impact: "The current local Kernel status has no cloud-connectivity projection.",
    },
  ];
}

export function adaptKernelStatus(
  payload: KernelStatusPayload,
  observedAt: string,
): OperationalWorkspace {
  const stages = payload.stages.map(stageView);
  const sessionMap = new Map<string, SessionView>();
  for (const rawStage of payload.stages) {
    for (const projection of [...rawStage.assembling_sessions, ...rawStage.recent_sessions]) {
      sessionMap.set(projection.session_id, sessionFromProjection(projection, rawStage));
    }
    const current = currentSessionFromStage(rawStage);
    if (current) sessionMap.set(current.id, current);
  }
  const attention = [
    ...globalAttention(payload),
    ...stages.flatMap((stage) => {
      const item = stageAttentionItem(stage);
      return item ? [item] : [];
    }),
  ];
  return {
    dataSource: {
      kind: "kernel",
      label: "Live Kernel status · read only",
      updatedAt: observedAt,
      authoritative: true,
    },
    event: {
      id: payload.event_id ?? undefined,
      key: payload.event_key ?? "unconfigured",
      name: payload.event_name ?? "StageFlow Kernel",
      lifecycle: payload.event_id && payload.ready ? "active" : "setup",
      modeLabel: "Event Mode · Kernel projection",
      ready: payload.ready,
      recovering: payload.recovering,
      databaseAvailable: payload.database_available,
      stageCount: stages.length,
    },
    stages,
    sessions: [...sessionMap.values()],
    attention,
    infrastructure: infrastructure(payload),
    editorialCandidates: [],
    mediaTimingEvidence: [],
    mediaTimingEvidenceStatus: "not_requested",
  };
}

export function kernelUnavailableWorkspace(
  observedAt: string,
  reason = "Kernel status endpoint unavailable",
): OperationalWorkspace {
  const workspace = adaptKernelStatus(
    {
      configured: true,
      configuration_supplied: true,
      configuration_valid: true,
      runtime_composed: false,
      event_id: null,
      event_key: null,
      event_name: "StageFlow Kernel",
      database_available: false,
      ready: false,
      recovering: false,
      reconciliation_status: null,
      reconciliation_started_at: null,
      reconciliation_completed_at: null,
      stages: [],
      attention_codes: [reason],
      startup_error: reason,
    },
    observedAt,
  );
  return {
    ...workspace,
    dataSource: {
      kind: "kernel",
      label: "Kernel connection unavailable · read only",
      updatedAt: observedAt,
      authoritative: false,
    },
    event: {
      ...workspace.event,
      ready: false,
      databaseAvailable: false,
    },
    attention: [
      {
        id: "kernel-connection-unavailable",
        level: "intervention",
        title: "Kernel connection unavailable",
        scope: "Producer client",
        since: "Current request",
        impact: "The Producer client cannot refresh authoritative Event state.",
        safeContinuation:
          "The backend and primary recording may continue independently; no cached state is shown.",
        action: "Restore the local frontend-to-backend connection and refresh status.",
      },
    ],
    infrastructure: [
      {
        id: "kernel-api",
        label: "Kernel status API",
        health: "unavailable",
        state: "Unreachable",
        impact: reason,
        attentionLevel: "intervention",
      },
      ...workspace.infrastructure.filter(
        (item) => item.id === "workers" || item.id === "internet",
      ),
    ],
    mediaTimingEvidence: [],
    mediaTimingEvidenceStatus: "unavailable",
  };
}
