CREATE TABLE IF NOT EXISTS stageflow.business_event (
    event_id uuid PRIMARY KEY,
    event_key text NOT NULL UNIQUE CHECK (btrim(event_key) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    external_references jsonb NOT NULL DEFAULT '{}'::jsonb,
    revision bigint NOT NULL CHECK (revision > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS stageflow.stage (
    stage_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    stage_key text NOT NULL CHECK (btrim(stage_key) <> ''),
    name text NOT NULL CHECK (btrim(name) <> ''),
    external_references jsonb NOT NULL DEFAULT '{}'::jsonb,
    revision bigint NOT NULL CHECK (revision > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    UNIQUE (event_id, stage_key),
    UNIQUE (stage_id, event_id)
);

CREATE TABLE IF NOT EXISTS stageflow.stage_source_binding (
    source_binding_key text PRIMARY KEY CHECK (btrim(source_binding_key) <> ''),
    stage_id uuid NOT NULL REFERENCES stageflow.stage(stage_id),
    source_reference text NOT NULL CHECK (btrim(source_reference) <> ''),
    revision bigint NOT NULL CHECK (revision > 0),
    updated_at timestamptz NOT NULL,
    UNIQUE (source_binding_key, stage_id)
);

CREATE TABLE IF NOT EXISTS stageflow.event_stage_bootstrap_operation (
    operation_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    request_digest text NOT NULL CHECK (length(request_digest) = 64),
    result_status text NOT NULL CHECK (result_status IN ('created', 'resolved', 'updated')),
    applied_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS stageflow.program_expectation (
    expectation_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    expectation_key text NOT NULL CHECK (btrim(expectation_key) <> ''),
    expected_stage_id uuid,
    title text NOT NULL CHECK (btrim(title) <> ''),
    speakers jsonb NOT NULL DEFAULT '[]'::jsonb,
    planned_start timestamptz,
    planned_end timestamptz,
    external_references jsonb NOT NULL DEFAULT '{}'::jsonb,
    revision bigint NOT NULL CHECK (revision > 0),
    recorded_at timestamptz NOT NULL,
    UNIQUE (event_id, expectation_key),
    UNIQUE (expectation_id, event_id),
    CHECK (planned_end IS NULL OR planned_start IS NULL OR planned_end >= planned_start),
    FOREIGN KEY (expected_stage_id, event_id)
        REFERENCES stageflow.stage(stage_id, event_id)
);

CREATE TABLE IF NOT EXISTS stageflow.program_expectation_revision (
    revision_id uuid PRIMARY KEY,
    expectation_id uuid NOT NULL REFERENCES stageflow.program_expectation(expectation_id),
    expectation_revision bigint NOT NULL CHECK (expectation_revision > 0),
    expected_stage_id uuid,
    title text NOT NULL,
    speakers jsonb NOT NULL,
    planned_start timestamptz,
    planned_end timestamptz,
    external_references jsonb NOT NULL,
    recorded_at timestamptz NOT NULL,
    UNIQUE (expectation_id, expectation_revision)
);

CREATE TABLE IF NOT EXISTS stageflow.session (
    session_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    stage_id uuid NOT NULL,
    program_expectation_id uuid,
    title text,
    activity_state text NOT NULL CHECK (
        activity_state IN ('presentation_active', 'presentation_ended')
    ),
    package_state text NOT NULL CHECK (
        package_state IN (
            'assembling', 'ready_for_review', 'in_review', 'complete',
            'correction_required'
        )
    ),
    authoritative_start timestamptz NOT NULL,
    authoritative_end timestamptz,
    package_revision bigint NOT NULL CHECK (package_revision > 0),
    revision bigint NOT NULL CHECK (revision > 0),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    FOREIGN KEY (stage_id, event_id) REFERENCES stageflow.stage(stage_id, event_id),
    FOREIGN KEY (program_expectation_id, event_id)
        REFERENCES stageflow.program_expectation(expectation_id, event_id),
    CHECK (authoritative_end IS NULL OR authoritative_end >= authoritative_start)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_session_per_stage
ON stageflow.session(stage_id)
WHERE activity_state = 'presentation_active';

CREATE TABLE IF NOT EXISTS stageflow.session_start_operation (
    operation_id uuid PRIMARY KEY,
    session_id uuid NOT NULL UNIQUE REFERENCES stageflow.session(session_id),
    request_digest text NOT NULL CHECK (length(request_digest) = 64),
    applied_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS stageflow.session_boundary_history (
    boundary_decision_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    boundary_kind text NOT NULL CHECK (boundary_kind IN ('start', 'end')),
    boundary_at timestamptz NOT NULL,
    epistemic_kind text NOT NULL CHECK (
        epistemic_kind IN ('observed', 'derived', 'inferred', 'declared', 'external')
    ),
    actor_id uuid,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    decided_at timestamptz NOT NULL,
    resulting_session_revision bigint NOT NULL CHECK (resulting_session_revision > 0)
);

CREATE TABLE IF NOT EXISTS stageflow.media_candidate (
    candidate_id uuid PRIMARY KEY,
    proposed_asset_id uuid NOT NULL UNIQUE,
    stage_id uuid NOT NULL REFERENCES stageflow.stage(stage_id),
    source_binding_key text NOT NULL,
    source_reference text NOT NULL CHECK (btrim(source_reference) <> ''),
    discovered_at timestamptz NOT NULL,
    last_observed_at timestamptz NOT NULL,
    registration_state text NOT NULL CHECK (
        registration_state IN ('discovered', 'stabilizing', 'ready', 'registered')
    ),
    revision bigint NOT NULL CHECK (revision > 0),
    CHECK (last_observed_at >= discovered_at),
    FOREIGN KEY (source_binding_key, stage_id)
        REFERENCES stageflow.stage_source_binding(source_binding_key, stage_id)
);

CREATE TABLE IF NOT EXISTS stageflow.media_resource_observation (
    observation_id uuid PRIMARY KEY,
    candidate_id uuid NOT NULL REFERENCES stageflow.media_candidate(candidate_id),
    observation_kind text NOT NULL CHECK (btrim(observation_kind) <> ''),
    epistemic_kind text NOT NULL CHECK (
        epistemic_kind IN ('observed', 'derived', 'inferred', 'declared', 'external')
    ),
    observed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    facts jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS stageflow.completed_media_asset_registry (
    asset_id uuid PRIMARY KEY,
    candidate_id uuid NOT NULL UNIQUE REFERENCES stageflow.media_candidate(candidate_id),
    manifest_id uuid NOT NULL UNIQUE,
    stage_id uuid NOT NULL REFERENCES stageflow.stage(stage_id),
    source_binding_key text NOT NULL,
    media_started_at timestamptz,
    media_ended_at timestamptz,
    registered_at timestamptz NOT NULL,
    CHECK (media_ended_at IS NULL OR media_started_at IS NULL OR media_ended_at >= media_started_at),
    FOREIGN KEY (source_binding_key, stage_id)
        REFERENCES stageflow.stage_source_binding(source_binding_key, stage_id)
);

CREATE TABLE IF NOT EXISTS stageflow.media_association (
    asset_id uuid PRIMARY KEY REFERENCES stageflow.completed_media_asset_registry(asset_id),
    association_status text NOT NULL CHECK (
        association_status IN ('associated', 'unresolved', 'conflict')
    ),
    session_id uuid REFERENCES stageflow.session(session_id),
    authority text NOT NULL CHECK (authority IN ('deterministic', 'human')),
    reason_codes jsonb NOT NULL,
    evidence_ids jsonb NOT NULL,
    actor_id uuid,
    revision bigint NOT NULL CHECK (revision > 0),
    decided_at timestamptz NOT NULL,
    CHECK (
        (association_status = 'associated' AND session_id IS NOT NULL)
        OR (association_status <> 'associated' AND session_id IS NULL)
    ),
    CHECK (authority <> 'human' OR actor_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS stageflow.media_association_history (
    association_history_id uuid PRIMARY KEY,
    asset_id uuid NOT NULL REFERENCES stageflow.completed_media_asset_registry(asset_id),
    association_revision bigint NOT NULL CHECK (association_revision > 0),
    association_status text NOT NULL,
    session_id uuid,
    authority text NOT NULL,
    reason_codes jsonb NOT NULL,
    evidence_ids jsonb NOT NULL,
    actor_id uuid,
    decided_at timestamptz NOT NULL,
    UNIQUE (asset_id, association_revision)
);

CREATE TABLE IF NOT EXISTS stageflow.session_completion_history (
    completion_decision_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    package_revision bigint NOT NULL CHECK (package_revision > 0),
    actor_id uuid NOT NULL,
    approved boolean NOT NULL,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    decided_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS stageflow.reconciliation_run (
    sequence bigserial UNIQUE NOT NULL,
    reconciliation_run_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    status text NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
    scope text NOT NULL CHECK (btrim(scope) <> ''),
    started_at timestamptz NOT NULL,
    completed_at timestamptz,
    candidates_seen bigint NOT NULL CHECK (candidates_seen >= 0),
    assets_registered bigint NOT NULL CHECK (assets_registered >= 0),
    failure_code text,
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

INSERT INTO stageflow.schema_migration (version)
VALUES ('0002_event_mode_kernel')
ON CONFLICT (version) DO NOTHING;
