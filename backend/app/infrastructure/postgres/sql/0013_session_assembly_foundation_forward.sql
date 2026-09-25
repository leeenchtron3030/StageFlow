CREATE TABLE stageflow.assembly_command (
    operation_id uuid PRIMARY KEY,
    command_kind text NOT NULL CHECK (command_kind IN ('template', 'proposal', 'decision')),
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    result_id uuid NOT NULL,
    actor_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL
);
CREATE TABLE stageflow.assembly_template (
    template_id uuid PRIMARY KEY,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    template_key text NOT NULL CHECK (btrim(template_key) <> '' AND length(template_key) <= 100),
    version bigint NOT NULL CHECK (version > 0),
    name text NOT NULL CHECK (btrim(name) <> '' AND length(name) <= 200),
    slots jsonb NOT NULL CHECK (jsonb_typeof(slots) = 'array' AND jsonb_array_length(slots) BETWEEN 1 AND 100),
    required_metadata jsonb NOT NULL CHECK (jsonb_typeof(required_metadata) = 'array'),
    created_at timestamptz NOT NULL,
    UNIQUE (event_id, template_key, version)
);
CREATE INDEX assembly_template_event_idx ON stageflow.assembly_template(event_id, template_id);
CREATE TABLE stageflow.assembly_revision (
    revision_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    revision_number bigint NOT NULL CHECK (revision_number > 0),
    supersedes_id uuid REFERENCES stageflow.assembly_revision(revision_id),
    template_id uuid NOT NULL REFERENCES stageflow.assembly_template(template_id),
    package_revision bigint NOT NULL CHECK (package_revision > 0),
    completion_decision_id uuid,
    validation_state text NOT NULL CHECK (validation_state IN ('valid', 'invalid')),
    validation_issues jsonb NOT NULL CHECK (jsonb_typeof(validation_issues) = 'array'),
    actor_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (session_id, revision_number),
    UNIQUE (revision_id, session_id),
    FOREIGN KEY (completion_decision_id, session_id, package_revision)
        REFERENCES stageflow.session_completion_history(completion_decision_id, session_id, package_revision),
    CHECK ((validation_state = 'valid') = (jsonb_array_length(validation_issues) = 0))
);
CREATE INDEX assembly_revision_event_idx ON stageflow.assembly_revision(event_id, session_id, revision_number);
CREATE TABLE stageflow.assembly_member (
    revision_id uuid NOT NULL REFERENCES stageflow.assembly_revision(revision_id),
    position integer NOT NULL CHECK (position >= 0),
    completion_decision_id uuid NOT NULL,
    asset_id uuid NOT NULL,
    association_revision bigint NOT NULL CHECK (association_revision > 0),
    media_started_at timestamptz,
    PRIMARY KEY (revision_id, position),
    UNIQUE (revision_id, asset_id),
    FOREIGN KEY (completion_decision_id, asset_id)
        REFERENCES stageflow.session_completion_asset(completion_decision_id, asset_id)
);
CREATE TABLE stageflow.assembly_binding (
    revision_id uuid NOT NULL REFERENCES stageflow.assembly_revision(revision_id),
    position integer NOT NULL CHECK (position >= 0),
    slot_key text NOT NULL,
    packaging_revision_id uuid REFERENCES stageflow.packaging_asset_revision(revision_id),
    outcome text NOT NULL CHECK (outcome IN ('bound', 'unresolved', 'ambiguous', 'invalid_explicit', 'session_media')),
    PRIMARY KEY (revision_id, position),
    UNIQUE (revision_id, slot_key),
    CHECK ((outcome = 'bound') = (packaging_revision_id IS NOT NULL))
);
CREATE TABLE stageflow.assembly_metadata_snapshot (
    revision_id uuid NOT NULL REFERENCES stageflow.assembly_revision(revision_id),
    field text NOT NULL CHECK (field IN ('session_title', 'participant_names')),
    values_json jsonb NOT NULL CHECK (jsonb_typeof(values_json) = 'array'),
    source text NOT NULL CHECK (source = 'program_expectation'),
    source_id uuid NOT NULL,
    source_revision bigint NOT NULL,
    PRIMARY KEY (revision_id, field),
    FOREIGN KEY (source_id, source_revision)
        REFERENCES stageflow.program_expectation_revision(expectation_id, expectation_revision)
);
CREATE TABLE stageflow.assembly_approval_decision (
    decision_id uuid PRIMARY KEY,
    session_id uuid NOT NULL,
    revision_id uuid NOT NULL,
    sequence bigint NOT NULL CHECK (sequence > 0),
    actor_id uuid NOT NULL,
    decided_at timestamptz NOT NULL,
    action text NOT NULL CHECK (action IN ('approve', 'reject')),
    reason text NOT NULL CHECK (btrim(reason) <> '' AND length(reason) <= 500),
    authority_kind text NOT NULL CHECK (authority_kind = 'human'),
    UNIQUE (session_id, sequence),
    FOREIGN KEY (revision_id, session_id) REFERENCES stageflow.assembly_revision(revision_id, session_id)
);
CREATE INDEX assembly_decision_revision_idx ON stageflow.assembly_approval_decision(revision_id, sequence DESC);
CREATE FUNCTION stageflow.assembly_history_is_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'assembly_history_is_immutable';
END;
$$;
CREATE TRIGGER assembly_template_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_template
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_revision_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_revision
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_member_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_member
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_binding_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_binding
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_metadata_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_metadata_snapshot
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_decision_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_approval_decision
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
CREATE TRIGGER assembly_command_immutable BEFORE UPDATE OR DELETE ON stageflow.assembly_command
    FOR EACH ROW EXECUTE FUNCTION stageflow.assembly_history_is_immutable();
INSERT INTO stageflow.schema_migration(version) VALUES ('0013_session_assembly_foundation');
