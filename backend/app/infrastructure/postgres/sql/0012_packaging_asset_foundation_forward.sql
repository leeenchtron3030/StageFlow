CREATE TABLE stageflow.packaging_asset_command (
    operation_id uuid PRIMARY KEY,
    command_kind text NOT NULL CHECK (command_kind IN (
        'packaging_asset_registration', 'packaging_asset_revision', 'packaging_asset_approval'
    )),
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    result_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL
);

CREATE TABLE stageflow.packaging_asset (
    packaging_asset_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    stage_id uuid,
    name text NOT NULL CHECK (btrim(name) <> '' AND length(name) <= 200),
    role text NOT NULL CHECK (role IN ('opening_bumper', 'title_card', 'sponsor_card', 'outro')),
    created_at timestamptz NOT NULL,
    FOREIGN KEY (stage_id, event_id) REFERENCES stageflow.stage(stage_id, event_id)
);
CREATE INDEX packaging_asset_event_idx ON stageflow.packaging_asset(event_id, packaging_asset_id);

CREATE TABLE stageflow.packaging_asset_revision (
    revision_id uuid PRIMARY KEY,
    packaging_asset_id uuid NOT NULL REFERENCES stageflow.packaging_asset(packaging_asset_id),
    revision_number bigint NOT NULL CHECK (revision_number > 0),
    content_kind text NOT NULL CHECK (content_kind IN ('external_content', 'completed_media_asset')),
    content_key text CHECK (content_key ~ '^[A-Za-z0-9][A-Za-z0-9_-]{0,199}$'),
    sha256 text CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size bigint CHECK (byte_size >= 0),
    media_type text CHECK (length(media_type) <= 127 AND
        media_type ~ '^[A-Za-z0-9!#$&^_+.-]+/[A-Za-z0-9!#$&^_+.-]+$'),
    completed_media_asset_id uuid REFERENCES stageflow.completed_media_asset_registry(asset_id),
    measured_duration_microseconds bigint CHECK (measured_duration_microseconds >= 0),
    effective_from timestamptz,
    effective_until timestamptz,
    created_at timestamptz NOT NULL,
    UNIQUE (packaging_asset_id, revision_number),
    CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until > effective_from),
    CHECK (
        (content_kind = 'external_content' AND content_key IS NOT NULL AND sha256 IS NOT NULL
         AND byte_size IS NOT NULL AND media_type IS NOT NULL AND completed_media_asset_id IS NULL)
        OR
        (content_kind = 'completed_media_asset' AND completed_media_asset_id IS NOT NULL
         AND content_key IS NULL AND sha256 IS NULL AND byte_size IS NULL AND media_type IS NULL)
    )
);

CREATE TABLE stageflow.packaging_asset_approval_decision (
    decision_id uuid PRIMARY KEY,
    packaging_asset_id uuid NOT NULL,
    revision_number bigint NOT NULL,
    decision_sequence bigint NOT NULL CHECK (decision_sequence > 0),
    actor_id uuid NOT NULL,
    decided_at timestamptz NOT NULL,
    action text NOT NULL CHECK (action IN ('approve', 'reject', 'revoke')),
    reason text NOT NULL CHECK (btrim(reason) <> '' AND length(reason) <= 500),
    UNIQUE (packaging_asset_id, decision_sequence),
    FOREIGN KEY (packaging_asset_id, revision_number)
        REFERENCES stageflow.packaging_asset_revision(packaging_asset_id, revision_number)
);
CREATE INDEX packaging_asset_approval_revision_idx
    ON stageflow.packaging_asset_approval_decision
        (packaging_asset_id, revision_number, decision_sequence DESC);

-- Enforce append-only history even for accidental adapter writes.
CREATE FUNCTION stageflow.packaging_asset_history_is_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'packaging_asset_history_is_immutable';
END;
$$;
CREATE TRIGGER packaging_asset_revision_immutable
    BEFORE UPDATE OR DELETE ON stageflow.packaging_asset_revision
    FOR EACH ROW EXECUTE FUNCTION stageflow.packaging_asset_history_is_immutable();
CREATE TRIGGER packaging_asset_approval_immutable
    BEFORE UPDATE OR DELETE ON stageflow.packaging_asset_approval_decision
    FOR EACH ROW EXECUTE FUNCTION stageflow.packaging_asset_history_is_immutable();

INSERT INTO stageflow.schema_migration(version) VALUES ('0012_packaging_asset_foundation');
