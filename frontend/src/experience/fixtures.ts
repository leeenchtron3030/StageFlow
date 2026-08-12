import type {
  AttentionItemView,
  EditorialCandidateView,
  InfrastructureItemView,
  OperationalWorkspace,
  ScenarioOption,
  SessionView,
  StageView,
} from "./model.ts";

const OBSERVED_AT = "2026-08-12T01:32:00-07:00";

export const scenarioOptions: ScenarioOption[] = [
  { id: "quiet", label: "A · Quiet healthy Event", group: "operational" },
  { id: "assembling", label: "B · Presentation ended", group: "operational" },
  { id: "turnover", label: "C · Unresolved turnover", group: "operational" },
  { id: "growing", label: "D · Transient file growth", group: "operational" },
  { id: "source-unavailable", label: "E · Source unavailable", group: "operational" },
  { id: "cloud-unavailable", label: "F · Cloud unavailable", group: "operational" },
  { id: "completed", label: "G · Completed Session", group: "operational" },
  { id: "run-002", label: "Run 002 · Baseline", group: "evidence" },
  { id: "run-003", label: "Run 003 · No Session authority", group: "evidence" },
  { id: "run-004", label: "Run 004 · Same-Stage turnover", group: "evidence" },
];

const baseInfrastructure: InfrastructureItemView[] = [
  {
    id: "postgresql",
    label: "PostgreSQL",
    health: "ready",
    state: "Ready",
    impact: "Authoritative Event and Session state available.",
    detail: "Latest reconciliation completed.",
  },
  {
    id: "sources",
    label: "Stage sources",
    health: "ready",
    state: "3 / 3 available",
    impact: "Configured local sources are observable.",
  },
  {
    id: "workers",
    label: "Intelligence",
    health: "unknown",
    state: "Not connected",
    impact: "Transcription and Moment generation are development placeholders.",
  },
  {
    id: "internet",
    label: "Internet",
    health: "ready",
    state: "Available",
    impact: "Optional cloud capability is reachable; local Event Mode remains primary.",
  },
];

function media(
  associated: number,
  stabilizing = 0,
  unresolved = 0,
  conflicting = 0,
  registered = associated + unresolved + conflicting,
) {
  return {
    discovered: registered + stabilizing,
    stabilizing,
    registered,
    associated,
    unresolved,
    conflicting,
    lastActivityAt: "2026-08-12T01:31:42-07:00",
  };
}

function session(
  id: string,
  title: string,
  stageKey: string,
  stageName: string,
  options: Partial<SessionView> = {},
): SessionView {
  return {
    id,
    title,
    stageKey,
    stageName,
    activityState: "presentation_active",
    packageState: "assembling",
    packageRevision: 1,
    sessionRevision: 2,
    authoritativeStart: "2026-08-12T01:02:00-07:00",
    media: media(29),
    provenance: "fixture",
    ...options,
  };
}

function stage(
  key: string,
  name: string,
  currentSession: SessionView | undefined,
  options: Partial<StageView> = {},
): StageView {
  return {
    id: `stage-${key}`,
    key,
    name,
    sourceState: "ready",
    sourceLabel: "Available",
    sourceImpact: "Local media observation continuing normally.",
    currentSession,
    media: currentSession?.media ?? media(0),
    ...options,
  };
}

const mainSession = session("session-main", "Scaling Ethereum", "main", "Main Stage", {
  media: media(32),
});
const studioSession = session(
  "session-studio",
  "Open Source Protocol Design",
  "studio",
  "Studio",
  { media: media(18, 1) },
);
const workshopSession = session(
  "session-workshop",
  "Community Coordination",
  "workshop",
  "Workshop",
  {
    activityState: "presentation_ended",
    authoritativeEnd: "2026-08-12T01:27:00-07:00",
    media: media(20, 1),
  },
);

const editorialCandidates: EditorialCandidateView[] = [
  {
    id: "candidate-1",
    sessionId: mainSession.id,
    sessionTitle: mainSession.title,
    stageName: mainSession.stageName,
    at: "18:42",
    origin: "producer",
    state: "priority",
    excerpt: "A producer-marked moment is ready for human Editorial review.",
    reason: "Declared by Producer · development fixture",
  },
  {
    id: "candidate-2",
    sessionId: studioSession.id,
    sessionTitle: studioSession.title,
    stageName: studioSession.stageName,
    at: "12:16",
    origin: "machine",
    state: "candidate",
    excerpt: "Machine Candidate content is intentionally synthetic in this shell.",
    reason: "Inferred · fixture only · no model execution",
  },
];

function quietWorkspace(): OperationalWorkspace {
  const main = structuredClone(mainSession);
  const studio = structuredClone(studioSession);
  const workshop = structuredClone(workshopSession);
  const stages = [
    stage("main", "Main Stage", main, { nextExpectation: "Protocol Economics" }),
    stage("studio", "Studio", studio, { nextExpectation: "Applied Cryptography" }),
    stage("workshop", "Workshop", workshop, {
      nextExpectation: "Developer Tooling",
    }),
  ];
  return {
    dataSource: {
      kind: "fixture",
      label: "Development fixture",
      scenarioId: "quiet",
      scenarioLabel: "Quiet healthy Event",
      updatedAt: OBSERVED_AT,
      authoritative: false,
    },
    event: {
      id: "event-fixture",
      key: "stageflow-review",
      name: "StageFlow Operator Review",
      lifecycle: "active",
      modeLabel: "Event Mode · Local first",
      ready: true,
      recovering: false,
      databaseAvailable: true,
      stageCount: stages.length,
    },
    stages,
    sessions: [main, studio, workshop],
    attention: [],
    infrastructure: structuredClone(baseInfrastructure),
    editorialCandidates: structuredClone(editorialCandidates),
    mediaTimingEvidence: [],
    mediaTimingEvidenceStatus: "available",
  };
}

function attention(
  id: string,
  level: AttentionItemView["level"],
  title: string,
  scope: string,
  impact: string,
  safeContinuation: string,
  action: string,
): AttentionItemView {
  return { id, level, title, scope, since: "01:24", impact, safeContinuation, action };
}

function assemblingWorkspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  const ended = session("session-main-ended", "Scaling Ethereum", "main", "Main Stage", {
    activityState: "presentation_ended",
    authoritativeEnd: "2026-08-12T01:25:18-07:00",
    packageState: "assembling",
    media: media(20, 1),
  });
  workspace.dataSource.scenarioId = "assembling";
  workspace.dataSource.scenarioLabel = "Presentation ended, media assembling";
  workspace.stages[0] = stage("main", "Main Stage", ended, {
    media: ended.media,
    nextExpectation: "Protocol Economics",
  });
  workspace.sessions = [ended, workspace.sessions[1], workspace.sessions[2]];
  return workspace;
}

function turnoverWorkspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  const previous = session("session-a", "Account Abstraction", "main", "Main Stage", {
    activityState: "presentation_ended",
    authoritativeEnd: "2026-08-12T01:21:39-07:00",
    packageState: "assembling",
    media: media(32),
  });
  const current = session("session-b", "Future of Ethereum", "main", "Main Stage", {
    authoritativeStart: "2026-08-12T01:24:56-07:00",
    media: media(0, 0, 17, 0, 17),
    attentionLevel: "review",
    attentionText: "17 media items cannot be safely assigned",
  });
  const item = attention(
    "turnover-review",
    "review",
    "Media association requires review",
    "Main Stage · Account Abstraction / Future of Ethereum",
    "17 registered media items have multiple eligible Sessions.",
    "Media is preserved. Session control and local processing continue.",
    "Review association when authoritative evidence is available.",
  );
  workspace.dataSource.scenarioId = "turnover";
  workspace.dataSource.scenarioLabel = "Unresolved same-Stage turnover";
  workspace.stages[0] = stage("main", "Main Stage", current, {
    previousSession: previous,
    media: media(32, 0, 17, 0, 49),
    attentionLevel: "review",
    attentionText: "17 unresolved · media preserved",
    nextExpectation: "Protocol Economics",
  });
  workspace.sessions = [current, previous, workspace.sessions[1], workspace.sessions[2]];
  workspace.attention = [item];
  return workspace;
}

function growingWorkspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  workspace.dataSource.scenarioId = "growing";
  workspace.dataSource.scenarioLabel = "Transient file growth";
  workspace.stages[1].media = media(18, 1);
  if (workspace.stages[1].currentSession) {
    workspace.stages[1].currentSession.media = workspace.stages[1].media;
  }
  workspace.infrastructure[1].detail = "One growing Candidate is stabilizing normally.";
  return workspace;
}

function sourceUnavailableWorkspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  const item = attention(
    "source-unavailable",
    "intervention",
    "Configured source unavailable",
    "Workshop",
    "StageFlow cannot observe new Workshop media from the configured source.",
    "Existing registered media and authoritative Session state remain preserved.",
    "Restore or verify the configured source before relying on new media ingestion.",
  );
  workspace.dataSource.scenarioId = "source-unavailable";
  workspace.dataSource.scenarioLabel = "Source unavailable";
  workspace.stages[2].sourceState = "unavailable";
  workspace.stages[2].sourceLabel = "Unavailable";
  workspace.stages[2].sourceImpact = "New local media cannot currently be observed.";
  workspace.stages[2].attentionLevel = "intervention";
  workspace.stages[2].attentionText = "Source unavailable";
  workspace.attention = [item];
  workspace.infrastructure[1] = {
    id: "sources",
    label: "Stage sources",
    health: "degraded",
    state: "2 / 3 available",
    impact: "Workshop media observation is unavailable; other Stages continue.",
    attentionLevel: "intervention",
  };
  return workspace;
}

function cloudUnavailableWorkspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  workspace.dataSource.scenarioId = "cloud-unavailable";
  workspace.dataSource.scenarioLabel = "Internet unavailable, local Event Mode continues";
  workspace.infrastructure[3] = {
    id: "internet",
    label: "Internet",
    health: "degraded",
    state: "Unavailable",
    impact: "Cloud enrichment deferred. Local Session control and media preservation continue.",
    attentionLevel: "information",
  };
  return workspace;
}

function completedWorkspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  const completed = session("session-complete", "Scaling Ethereum", "main", "Main Stage", {
    activityState: "presentation_ended",
    packageState: "complete",
    packageRevision: 1,
    sessionRevision: 4,
    authoritativeEnd: "2026-08-12T01:26:22-07:00",
    completedAt: "2026-08-12T01:31:02-07:00",
    media: media(20),
  });
  workspace.dataSource.scenarioId = "completed";
  workspace.dataSource.scenarioLabel = "Completed Session";
  workspace.stages[0] = stage("main", "Main Stage", undefined, {
    previousSession: completed,
    media: media(20),
    nextExpectation: "Protocol Economics",
  });
  workspace.sessions = [workspace.sessions[1], workspace.sessions[2], completed];
  return workspace;
}

function run002Workspace(): OperationalWorkspace {
  const workspace = assemblingWorkspace();
  const run = session("run-002-session", "Run 002 reference Session", "main", "Main Stage", {
    activityState: "presentation_ended",
    packageState: "complete",
    packageRevision: 1,
    sessionRevision: 4,
    authoritativeStart: "2026-08-10T13:10:29-07:00",
    authoritativeEnd: "2026-08-10T13:26:22-07:00",
    media: media(20),
  });
  workspace.dataSource.scenarioId = "run-002";
  workspace.dataSource.scenarioLabel = "Sanitized Run 002 baseline";
  workspace.stages = [stage("main", "Main Stage", undefined, { previousSession: run, media: run.media })];
  workspace.sessions = [run];
  workspace.event.stageCount = 1;
  workspace.editorialCandidates = [];
  return workspace;
}

function run003Workspace(): OperationalWorkspace {
  const workspace = quietWorkspace();
  const item = attention(
    "no-session-authority",
    "review",
    "Media has no realized Session authority",
    "Main Stage",
    "35 registered media items remain unresolved because no Session was realized.",
    "Media is preserved. StageFlow did not invent Session authority.",
    "Realize or identify the correct Session before human assignment.",
  );
  workspace.dataSource.scenarioId = "run-003";
  workspace.dataSource.scenarioLabel = "Sanitized Run 003 no-authority evidence";
  workspace.stages = [
    stage("main", "Main Stage", undefined, {
      media: media(0, 0, 35, 0, 35),
      attentionLevel: "review",
      attentionText: "35 unresolved · no Session authority",
      nextExpectation: "External Program Expectation A / B",
    }),
  ];
  workspace.sessions = [];
  workspace.attention = [item];
  workspace.event.stageCount = 1;
  workspace.editorialCandidates = [];
  return workspace;
}

function run004Workspace(): OperationalWorkspace {
  const workspace = turnoverWorkspace();
  workspace.dataSource.scenarioId = "run-004";
  workspace.dataSource.scenarioLabel = "Sanitized Run 004 turnover evidence";
  if (workspace.stages[0].currentSession) {
    workspace.stages[0].currentSession.activityState = "presentation_ended";
    workspace.stages[0].currentSession.authoritativeEnd = "2026-08-12T01:39:17-07:00";
  }
  workspace.stages = [workspace.stages[0]];
  workspace.sessions = workspace.sessions.slice(0, 2);
  workspace.event.stageCount = 1;
  workspace.editorialCandidates = [];
  workspace.mediaTimingEvidence = [
    {
      evidenceId: "mte-run-004-001",
      assetId: "asset-run-004-001",
      stageKey: "main",
      revision: 1,
      candidateStartedAt: "2026-08-12T01:24:01-07:00",
      candidateEndedAt: "2026-08-12T01:25:01.030-07:00",
      evidenceLabel: "Observed vMix recorder/container metadata",
      derivationLabel: "creation_time + measured duration · rule 1.0",
      qualificationStatus: "unqualified",
      recorderProfileLabel: "vMix reference profile · revision 1",
      precision: "microsecond representation; content-start semantics unqualified",
      limitations: [
        "Candidate interval is Derived, not authoritative Session or content time.",
        "Controlled content-time calibration has not passed.",
      ],
      authorizedUse: "advisory_only",
    },
  ];
  return workspace;
}

const builders: Record<string, () => OperationalWorkspace> = {
  quiet: quietWorkspace,
  assembling: assemblingWorkspace,
  turnover: turnoverWorkspace,
  growing: growingWorkspace,
  "source-unavailable": sourceUnavailableWorkspace,
  "cloud-unavailable": cloudUnavailableWorkspace,
  completed: completedWorkspace,
  "run-002": run002Workspace,
  "run-003": run003Workspace,
  "run-004": run004Workspace,
};

export function getFixtureWorkspace(scenarioId = "quiet"): OperationalWorkspace {
  const resolved = builders[scenarioId] ? scenarioId : "quiet";
  return builders[resolved]();
}
