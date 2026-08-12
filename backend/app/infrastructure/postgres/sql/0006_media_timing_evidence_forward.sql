CREATE TABLE IF NOT EXISTS stageflow.media_timing_evidence (
    evidence_id uuid PRIMARY KEY,
    asset_id uuid NOT NULL REFERENCES stageflow.completed_media_asset_registry(asset_id),
    manifest_id uuid NOT NULL,
    manifest_version text NOT NULL CHECK (btrim(manifest_version) <> ''),
    evidence_revision bigint NOT NULL CHECK (evidence_revision > 0),
    predecessor_evidence_id uuid,
    provider_id text NOT NULL CHECK (btrim(provider_id) <> ''),
    provider_version text NOT NULL CHECK (btrim(provider_version) <> ''),
    tool_id text NOT NULL CHECK (btrim(tool_id) <> ''),
    tool_version text NOT NULL CHECK (btrim(tool_version) <> ''),
    recorder_profile_id text NOT NULL CHECK (btrim(recorder_profile_id) <> ''),
    recorder_profile_revision bigint NOT NULL CHECK (recorder_profile_revision > 0),
    inspected_at timestamptz NOT NULL,
    qualification_status text NOT NULL CHECK (
        qualification_status IN ('unqualified', 'qualified', 'rejected', 'expired')
    ),
    qualification_evaluated_at timestamptz NOT NULL,
    qualification_record_id uuid,
    qualification_limitations text[] NOT NULL DEFAULT '{}',
    limitations text[] NOT NULL DEFAULT '{}',
    applied_at timestamptz NOT NULL,
    UNIQUE (asset_id, evidence_revision),
    UNIQUE (asset_id, evidence_id),
    FOREIGN KEY (asset_id, predecessor_evidence_id)
        REFERENCES stageflow.media_timing_evidence(asset_id, evidence_id),
    CHECK (applied_at >= inspected_at),
    CHECK (
        (qualification_status = 'qualified' AND qualification_record_id IS NOT NULL)
        OR qualification_status <> 'qualified'
    ),
    CHECK (
        (evidence_revision = 1 AND predecessor_evidence_id IS NULL)
        OR (evidence_revision > 1 AND predecessor_evidence_id IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS stageflow.media_timing_observation (
    evidence_id uuid NOT NULL REFERENCES stageflow.media_timing_evidence(evidence_id),
    observation_id uuid NOT NULL,
    observation_kind text NOT NULL CHECK (btrim(observation_kind) <> ''),
    epistemic_kind text NOT NULL DEFAULT 'observed' CHECK (epistemic_kind = 'observed'),
    source_field text NOT NULL CHECK (btrim(source_field) <> ''),
    original_representation text NOT NULL CHECK (btrim(original_representation) <> ''),
    observed_at timestamptz NOT NULL,
    timezone_kind text NOT NULL CHECK (
        timezone_kind IN (
            'explicit_utc', 'explicit_offset', 'naive_unqualified', 'not_applicable'
        )
    ),
    normalized_timestamp timestamptz,
    normalized_duration_microseconds bigint CHECK (
        normalized_duration_microseconds IS NULL
        OR normalized_duration_microseconds >= 0
    ),
    normalized_value text,
    precision text,
    stream_selector text,
    limitations text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, observation_id),
    CHECK (
        num_nonnulls(
            normalized_timestamp,
            normalized_duration_microseconds,
            normalized_value
        ) <= 1
    ),
    CHECK (
        timezone_kind <> 'naive_unqualified'
        OR normalized_timestamp IS NULL
    )
);

CREATE TABLE IF NOT EXISTS stageflow.media_timing_derivation (
    evidence_id uuid NOT NULL REFERENCES stageflow.media_timing_evidence(evidence_id),
    derivation_id uuid NOT NULL,
    epistemic_kind text NOT NULL DEFAULT 'derived' CHECK (epistemic_kind = 'derived'),
    rule_id text NOT NULL CHECK (btrim(rule_id) <> ''),
    rule_version text NOT NULL CHECK (btrim(rule_version) <> ''),
    candidate_started_at timestamptz NOT NULL,
    candidate_ended_at timestamptz NOT NULL,
    derived_at timestamptz NOT NULL,
    limitations text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (evidence_id, derivation_id),
    CHECK (candidate_ended_at >= candidate_started_at)
);

CREATE TABLE IF NOT EXISTS stageflow.media_timing_derivation_input (
    evidence_id uuid NOT NULL,
    derivation_id uuid NOT NULL,
    observation_id uuid NOT NULL,
    PRIMARY KEY (evidence_id, derivation_id, observation_id),
    FOREIGN KEY (evidence_id, derivation_id)
        REFERENCES stageflow.media_timing_derivation(evidence_id, derivation_id),
    FOREIGN KEY (evidence_id, observation_id)
        REFERENCES stageflow.media_timing_observation(evidence_id, observation_id)
);

CREATE TABLE IF NOT EXISTS stageflow.media_timing_evidence_application (
    operation_id uuid PRIMARY KEY,
    request_digest text NOT NULL CHECK (
        request_digest ~ '^[0-9a-f]{64}$'
    ),
    evidence_id uuid NOT NULL UNIQUE REFERENCES stageflow.media_timing_evidence(evidence_id),
    recorded_at timestamptz NOT NULL
);

INSERT INTO stageflow.schema_migration (version)
VALUES ('0006_media_timing_evidence')
ON CONFLICT (version) DO NOTHING;
