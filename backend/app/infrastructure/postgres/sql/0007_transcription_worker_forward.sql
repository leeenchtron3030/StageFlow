CREATE TABLE IF NOT EXISTS stageflow.work_worker (
    worker_id uuid PRIMARY KEY,
    node_id text NOT NULL CHECK (btrim(node_id) <> ''),
    deployment_id text NOT NULL CHECK (btrim(deployment_id) <> ''),
    event_id uuid REFERENCES stageflow.business_event(event_id),
    enabled boolean NOT NULL,
    draining boolean NOT NULL,
    implementation_version text NOT NULL CHECK (btrim(implementation_version) <> ''),
    revision bigint NOT NULL CHECK (revision > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (updated_at >= created_at),
    CHECK (NOT draining OR enabled)
);

CREATE TABLE IF NOT EXISTS stageflow.work_worker_capability (
    capability_id uuid PRIMARY KEY,
    worker_id uuid NOT NULL REFERENCES stageflow.work_worker(worker_id),
    operation_kind text NOT NULL CHECK (operation_kind = 'transcription'),
    operation_schema_version text NOT NULL CHECK (btrim(operation_schema_version) <> ''),
    execution_profile_id text NOT NULL CHECK (btrim(execution_profile_id) <> ''),
    execution_profile_version text NOT NULL CHECK (btrim(execution_profile_version) <> ''),
    locality text NOT NULL CHECK (locality IN ('local', 'cloud')),
    accepted_asset_formats text[] NOT NULL CHECK (
        cardinality(accepted_asset_formats) > 0
    ),
    supports_word_timing boolean NOT NULL,
    supports_speaker_labels boolean NOT NULL,
    provider_id text,
    provider_version text,
    model_id text,
    model_version text,
    runtime_id text NOT NULL CHECK (btrim(runtime_id) <> ''),
    runtime_version text NOT NULL CHECK (btrim(runtime_version) <> ''),
    configured_eligible boolean NOT NULL,
    effective_from timestamptz NOT NULL,
    effective_until timestamptz,
    CHECK (effective_until IS NULL OR effective_until > effective_from),
    CHECK ((provider_id IS NULL) = (provider_version IS NULL)),
    CHECK ((model_id IS NULL) = (model_version IS NULL))
);

CREATE INDEX IF NOT EXISTS work_worker_capability_match_idx
    ON stageflow.work_worker_capability (
        worker_id,
        operation_kind,
        operation_schema_version,
        execution_profile_id,
        execution_profile_version,
        configured_eligible
    );

CREATE TABLE IF NOT EXISTS stageflow.work_worker_presence (
    worker_id uuid PRIMARY KEY REFERENCES stageflow.work_worker(worker_id),
    observed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    maximum_concurrency integer NOT NULL CHECK (
        maximum_concurrency BETWEEN 1 AND 64
    ),
    health_state text NOT NULL CHECK (
        health_state IN ('available', 'degraded', 'unavailable', 'unknown')
    ),
    pressure_state text NOT NULL CHECK (
        pressure_state IN ('normal', 'constrained', 'saturated', 'unknown')
    ),
    CHECK (expires_at > observed_at)
);

CREATE TABLE IF NOT EXISTS stageflow.work_operation (
    operation_id uuid PRIMARY KEY,
    operation_kind text NOT NULL CHECK (operation_kind = 'transcription'),
    operation_schema_version text NOT NULL CHECK (
        btrim(operation_schema_version) <> ''
    ),
    deployment_id text NOT NULL CHECK (btrim(deployment_id) <> ''),
    event_id uuid REFERENCES stageflow.business_event(event_id),
    asset_id uuid NOT NULL REFERENCES stageflow.completed_media_asset_registry(asset_id),
    manifest_id uuid NOT NULL,
    manifest_version text NOT NULL CHECK (btrim(manifest_version) <> ''),
    asset_format text NOT NULL CHECK (btrim(asset_format) <> ''),
    execution_profile_id text NOT NULL CHECK (btrim(execution_profile_id) <> ''),
    execution_profile_version text NOT NULL CHECK (
        btrim(execution_profile_version) <> ''
    ),
    requested_language text,
    request_word_timing boolean NOT NULL,
    request_speaker_labels boolean NOT NULL,
    requires_cloud boolean NOT NULL,
    required_for_event boolean NOT NULL,
    idempotency_key text NOT NULL UNIQUE CHECK (btrim(idempotency_key) <> ''),
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    work_key text NOT NULL UNIQUE CHECK (work_key ~ '^[0-9a-f]{64}$'),
    priority integer NOT NULL CHECK (priority BETWEEN -1000 AND 1000),
    eligible_at timestamptz NOT NULL,
    operation_status text NOT NULL CHECK (
        operation_status IN (
            'pending', 'eligible', 'leased', 'running', 'retry_wait',
            'deferred', 'blocked', 'succeeded', 'terminal_failed',
            'cancel_requested', 'cancelled'
        )
    ),
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 20),
    retry_delay_microseconds bigint NOT NULL CHECK (
        retry_delay_microseconds > 0
        AND retry_delay_microseconds <= 3600000000
    ),
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    fence_generation bigint NOT NULL DEFAULT 0 CHECK (fence_generation >= 0),
    current_attempt_id uuid,
    lease_owner_worker_id uuid REFERENCES stageflow.work_worker(worker_id),
    lease_expires_at timestamptz,
    cancellation_requested_at timestamptz,
    terminal_result_type text,
    terminal_result_id uuid,
    terminal_result_revision bigint CHECK (
        terminal_result_revision IS NULL OR terminal_result_revision > 0
    ),
    last_reason_code text,
    row_revision bigint NOT NULL DEFAULT 1 CHECK (row_revision > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (updated_at >= created_at),
    CHECK (attempt_count <= max_attempts),
    CHECK (
        operation_status IN ('leased', 'running', 'cancel_requested')
        OR (
            current_attempt_id IS NULL
            AND lease_owner_worker_id IS NULL
            AND lease_expires_at IS NULL
        )
    ),
    CHECK (
        operation_status NOT IN ('leased', 'running')
        OR (
            current_attempt_id IS NOT NULL
            AND lease_owner_worker_id IS NOT NULL
            AND lease_expires_at IS NOT NULL
        )
    ),
    CHECK (
        operation_status <> 'succeeded'
        OR (
            terminal_result_type IS NOT NULL
            AND terminal_result_id IS NOT NULL
            AND terminal_result_revision IS NOT NULL
        )
    )
);

CREATE INDEX IF NOT EXISTS work_operation_claim_idx
    ON stageflow.work_operation (
        deployment_id,
        operation_status,
        priority DESC,
        eligible_at,
        created_at
    );

CREATE INDEX IF NOT EXISTS work_operation_expired_lease_idx
    ON stageflow.work_operation (lease_expires_at)
    WHERE operation_status IN ('leased', 'running', 'cancel_requested');

CREATE TABLE IF NOT EXISTS stageflow.work_operation_attempt (
    attempt_id uuid PRIMARY KEY,
    operation_id uuid NOT NULL REFERENCES stageflow.work_operation(operation_id),
    worker_id uuid NOT NULL REFERENCES stageflow.work_worker(worker_id),
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    fence_generation bigint NOT NULL CHECK (fence_generation > 0),
    attempt_status text NOT NULL CHECK (
        attempt_status IN ('leased', 'running', 'finalized')
    ),
    lease_started_at timestamptz NOT NULL,
    lease_expires_at timestamptz NOT NULL,
    execution_started_at timestamptz,
    finalized_at timestamptz,
    outcome text CHECK (
        outcome IN (
            'succeeded', 'retryable_failure', 'terminal_failure', 'lease_lost',
            'result_reconciled', 'cancelled', 'orphaned'
        )
    ),
    retryable boolean,
    reason_code text,
    diagnostic_summary text CHECK (
        diagnostic_summary IS NULL OR length(diagnostic_summary) <= 256
    ),
    created_at timestamptz NOT NULL,
    UNIQUE (operation_id, attempt_number),
    UNIQUE (operation_id, fence_generation),
    CHECK (lease_expires_at > lease_started_at),
    CHECK (
        attempt_status = 'finalized'
        OR (finalized_at IS NULL AND outcome IS NULL AND retryable IS NULL)
    ),
    CHECK (
        attempt_status <> 'finalized'
        OR (finalized_at IS NOT NULL AND outcome IS NOT NULL)
    )
);

ALTER TABLE stageflow.work_operation
    ADD CONSTRAINT work_operation_current_attempt_fk
    FOREIGN KEY (current_attempt_id)
    REFERENCES stageflow.work_operation_attempt(attempt_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS work_operation_attempt_active_idx
    ON stageflow.work_operation_attempt (lease_expires_at)
    WHERE attempt_status IN ('leased', 'running');

CREATE TABLE IF NOT EXISTS stageflow.transcript_evidence_revision (
    evidence_id uuid PRIMARY KEY,
    operation_id uuid NOT NULL UNIQUE
        REFERENCES stageflow.work_operation(operation_id),
    work_key text NOT NULL UNIQUE CHECK (work_key ~ '^[0-9a-f]{64}$'),
    result_digest text NOT NULL CHECK (result_digest ~ '^[0-9a-f]{64}$'),
    asset_id uuid NOT NULL REFERENCES stageflow.completed_media_asset_registry(asset_id),
    manifest_id uuid NOT NULL,
    manifest_version text NOT NULL CHECK (btrim(manifest_version) <> ''),
    evidence_revision bigint NOT NULL CHECK (evidence_revision > 0),
    predecessor_evidence_id uuid,
    evidence_status text NOT NULL CHECK (
        evidence_status IN ('complete', 'partial', 'failed')
    ),
    provider_id text NOT NULL CHECK (btrim(provider_id) <> ''),
    provider_version text NOT NULL CHECK (btrim(provider_version) <> ''),
    model_id text NOT NULL CHECK (btrim(model_id) <> ''),
    model_version text NOT NULL CHECK (btrim(model_version) <> ''),
    execution_tool_id text NOT NULL CHECK (btrim(execution_tool_id) <> ''),
    execution_tool_version text NOT NULL CHECK (btrim(execution_tool_version) <> ''),
    execution_revision text NOT NULL CHECK (btrim(execution_revision) <> ''),
    language text,
    produced_at timestamptz NOT NULL,
    applied_at timestamptz NOT NULL,
    partial_reason text,
    failure_reason text,
    limitations text[] NOT NULL DEFAULT '{}',
    UNIQUE (asset_id, evidence_revision),
    UNIQUE (asset_id, evidence_id),
    FOREIGN KEY (asset_id, predecessor_evidence_id)
        REFERENCES stageflow.transcript_evidence_revision(asset_id, evidence_id),
    CHECK (applied_at >= produced_at),
    CHECK (
        (evidence_revision = 1 AND predecessor_evidence_id IS NULL)
        OR (evidence_revision > 1 AND predecessor_evidence_id IS NOT NULL)
    ),
    CHECK (
        (evidence_status = 'complete'
            AND partial_reason IS NULL AND failure_reason IS NULL)
        OR (evidence_status = 'partial'
            AND partial_reason IS NOT NULL AND failure_reason IS NULL)
        OR (evidence_status = 'failed'
            AND partial_reason IS NULL AND failure_reason IS NOT NULL)
    )
);

ALTER TABLE stageflow.work_operation
    ADD CONSTRAINT work_operation_terminal_result_fk
    FOREIGN KEY (terminal_result_id)
    REFERENCES stageflow.transcript_evidence_revision(evidence_id)
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE IF NOT EXISTS stageflow.transcript_evidence_segment (
    evidence_id uuid NOT NULL
        REFERENCES stageflow.transcript_evidence_revision(evidence_id),
    segment_id uuid NOT NULL,
    segment_ordinal integer NOT NULL CHECK (segment_ordinal >= 0),
    epistemic_kind text NOT NULL DEFAULT 'observed' CHECK (
        epistemic_kind = 'observed'
    ),
    transcript_text text NOT NULL CHECK (btrim(transcript_text) <> ''),
    asset_start_microseconds bigint NOT NULL CHECK (
        asset_start_microseconds >= 0
    ),
    asset_end_microseconds bigint NOT NULL CHECK (
        asset_end_microseconds >= asset_start_microseconds
    ),
    speaker_label text,
    speaker_evidence_kind text CHECK (
        speaker_evidence_kind IN (
            'provider_inferred', 'provider_declared', 'unknown'
        )
    ),
    confidence double precision CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    ),
    confidence_semantics text,
    limitations text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, segment_id),
    UNIQUE (evidence_id, segment_ordinal),
    CHECK ((speaker_label IS NULL) = (speaker_evidence_kind IS NULL)),
    CHECK ((confidence IS NULL) = (confidence_semantics IS NULL))
);

CREATE TABLE IF NOT EXISTS stageflow.transcript_evidence_word (
    evidence_id uuid NOT NULL,
    segment_id uuid NOT NULL,
    word_id uuid NOT NULL,
    word_ordinal integer NOT NULL CHECK (word_ordinal >= 0),
    epistemic_kind text NOT NULL DEFAULT 'observed' CHECK (
        epistemic_kind = 'observed'
    ),
    word_text text NOT NULL CHECK (btrim(word_text) <> ''),
    asset_start_microseconds bigint NOT NULL CHECK (
        asset_start_microseconds >= 0
    ),
    asset_end_microseconds bigint NOT NULL CHECK (
        asset_end_microseconds >= asset_start_microseconds
    ),
    confidence double precision CHECK (
        confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
    ),
    confidence_semantics text,
    limitations text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, segment_id, word_id),
    UNIQUE (evidence_id, segment_id, word_ordinal),
    FOREIGN KEY (evidence_id, segment_id)
        REFERENCES stageflow.transcript_evidence_segment(evidence_id, segment_id),
    CHECK ((confidence IS NULL) = (confidence_semantics IS NULL))
);

CREATE TABLE IF NOT EXISTS stageflow.transcript_evidence_alignment (
    evidence_id uuid NOT NULL,
    segment_id uuid NOT NULL,
    alignment_id uuid NOT NULL,
    media_timing_evidence_id uuid NOT NULL
        REFERENCES stageflow.media_timing_evidence(evidence_id),
    epistemic_kind text NOT NULL DEFAULT 'derived' CHECK (
        epistemic_kind = 'derived'
    ),
    qualification_status text NOT NULL CHECK (
        qualification_status IN ('unqualified', 'qualified', 'rejected', 'expired')
    ),
    wall_clock_started_at timestamptz NOT NULL,
    wall_clock_ended_at timestamptz NOT NULL,
    derived_at timestamptz NOT NULL,
    limitations text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, segment_id),
    UNIQUE (alignment_id),
    FOREIGN KEY (evidence_id, segment_id)
        REFERENCES stageflow.transcript_evidence_segment(evidence_id, segment_id),
    CHECK (wall_clock_ended_at >= wall_clock_started_at)
);

INSERT INTO stageflow.schema_migration (version)
VALUES ('0007_transcription_worker')
ON CONFLICT (version) DO NOTHING;

