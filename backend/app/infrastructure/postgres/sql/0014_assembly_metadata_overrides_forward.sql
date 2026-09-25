CREATE TABLE stageflow.assembly_metadata_override (
    override_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    field text NOT NULL CHECK (field IN ('session_title', 'participant_names')),
    action text NOT NULL CHECK (action IN ('set', 'clear')),
    values_json jsonb NOT NULL CHECK (jsonb_typeof(values_json) = 'array'),
    sequence bigint NOT NULL CHECK (sequence > 0),
    actor_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL,
    reason text NOT NULL CHECK (btrim(reason) <> '' AND length(reason) <= 500),
    authority_kind text NOT NULL CHECK (authority_kind = 'human'),
    operation_id uuid NOT NULL UNIQUE,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    UNIQUE (session_id, sequence),
    UNIQUE (override_id, field),
    CHECK ((action = 'set' AND jsonb_array_length(values_json) BETWEEN 1 AND 100)
        OR (action = 'clear' AND jsonb_array_length(values_json) = 0))
);
CREATE INDEX assembly_metadata_override_latest_idx
    ON stageflow.assembly_metadata_override(session_id, field, sequence DESC);
CREATE TABLE stageflow.assembly_metadata_override_snapshot (
    revision_id uuid NOT NULL REFERENCES stageflow.assembly_revision(revision_id),
    field text NOT NULL CHECK (field IN ('session_title', 'participant_names')),
    override_id uuid NOT NULL,
    PRIMARY KEY (revision_id, field),
    FOREIGN KEY (override_id, field)
        REFERENCES stageflow.assembly_metadata_override(override_id, field)
);
CREATE TRIGGER assembly_metadata_override_immutable
    BEFORE UPDATE OR DELETE ON stageflow.assembly_metadata_override
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_metadata_override_snapshot_immutable
    BEFORE UPDATE OR DELETE ON stageflow.assembly_metadata_override_snapshot
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
INSERT INTO stageflow.schema_migration(version) VALUES ('0014_assembly_metadata_overrides');
