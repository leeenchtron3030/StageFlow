-- Advisory, append-only production context. No Kernel table or authority change.
CREATE TABLE stageflow.session_suggestion_run (
    run_id uuid PRIMARY KEY,
    run_sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    event_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    input_digest text NOT NULL CHECK (input_digest ~ '^[0-9a-f]{64}$'),
    actor_id uuid NOT NULL,
    created_at timestamptz NOT NULL,
    expectation_references jsonb NOT NULL CHECK (jsonb_typeof(expectation_references) = 'array'),
    asset_inputs jsonb NOT NULL CHECK (jsonb_typeof(asset_inputs) = 'array'),
    start_cue_list_id uuid,
    start_cue_list_version integer,
    end_cue_list_id uuid,
    end_cue_list_version integer,
    policy_id text NOT NULL CHECK (policy_id = 'boundary-suggestion'),
    policy_version text NOT NULL CHECK (policy_version = '1'),
    policy_constants jsonb NOT NULL CHECK (policy_constants = '{
        "id":"boundary-suggestion", "version":"1", "freeze_merge_seconds":15,
        "changeover_seconds":30, "edge_window_seconds":1200, "minimum_session_seconds":60,
        "cue_tie_seconds":60, "start_cue_before_seconds":120, "start_cue_after_seconds":180,
        "end_cue_before_seconds":180, "end_cue_after_seconds":60,
        "unscheduled_seconds":120, "clock_margin_seconds":43200
    }'::jsonb),
    no_timing_evidence integer NOT NULL CHECK (no_timing_evidence >= 0),
    no_segmentation integer NOT NULL CHECK (no_segmentation >= 0),
    clock_implausible integer NOT NULL CHECK (clock_implausible >= 0),
    no_coverage integer NOT NULL CHECK (no_coverage >= 0),
    no_planned_time integer NOT NULL CHECK (no_planned_time >= 0),
    FOREIGN KEY (stage_id, event_id) REFERENCES stageflow.stage(stage_id, event_id),
    FOREIGN KEY (start_cue_list_id, start_cue_list_version)
        REFERENCES stageflow.editorial_phrase_list(phrase_list_id, version) MATCH FULL,
    FOREIGN KEY (end_cue_list_id, end_cue_list_version)
        REFERENCES stageflow.editorial_phrase_list(phrase_list_id, version) MATCH FULL,
    UNIQUE (run_id, event_id, stage_id, policy_id, policy_version)
);
CREATE INDEX session_suggestion_run_stage_idx
    ON stageflow.session_suggestion_run(stage_id, run_sequence DESC);
CREATE INDEX session_suggestion_run_input_idx
    ON stageflow.session_suggestion_run(stage_id, input_digest);

CREATE TABLE stageflow.session_suggestion (
    suggestion_id uuid PRIMARY KEY,
    run_id uuid NOT NULL,
    event_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    expectation_id uuid,
    expectation_revision bigint,
    suggested_start timestamptz NOT NULL,
    suggested_end timestamptz NOT NULL CHECK (suggested_end > suggested_start + interval '60 seconds'),
    start_edge_kind text NOT NULL CHECK (start_edge_kind IN ('freeze', 'gap', 'coverage', 'schedule')),
    end_edge_kind text NOT NULL CHECK (end_edge_kind IN ('freeze', 'gap', 'coverage', 'schedule')),
    start_plan_offset_seconds double precision,
    end_plan_offset_seconds double precision,
    start_silence_support boolean NOT NULL,
    end_silence_support boolean NOT NULL,
    start_cue_support boolean NOT NULL,
    end_cue_support boolean NOT NULL,
    overlap boolean NOT NULL,
    strength text NOT NULL CHECK (strength IN ('strong', 'medium', 'weak')),
    timing_qualifications text[] NOT NULL CHECK (
        cardinality(timing_qualifications) > 0 AND
        timing_qualifications <@ ARRAY['unqualified', 'qualified', 'rejected', 'expired']),
    timing_references jsonb NOT NULL CHECK (jsonb_typeof(timing_references) = 'array'),
    segmentation_ids uuid[] NOT NULL,
    transcript_references jsonb NOT NULL CHECK (jsonb_typeof(transcript_references) = 'array'),
    policy_id text NOT NULL,
    policy_version text NOT NULL,
    FOREIGN KEY (run_id, event_id, stage_id, policy_id, policy_version)
        REFERENCES stageflow.session_suggestion_run(run_id, event_id, stage_id, policy_id, policy_version),
    FOREIGN KEY (expectation_id, expectation_revision)
        REFERENCES stageflow.program_expectation_revision(expectation_id, expectation_revision) MATCH FULL,
    CHECK ((expectation_id IS NULL AND start_plan_offset_seconds IS NULL AND end_plan_offset_seconds IS NULL)
        OR (expectation_id IS NOT NULL AND start_plan_offset_seconds IS NOT NULL AND end_plan_offset_seconds IS NOT NULL)),
    CHECK (strength = CASE
        WHEN expectation_id IS NULL OR overlap OR start_edge_kind = 'schedule' OR end_edge_kind = 'schedule'
            THEN 'weak'
        WHEN start_silence_support OR end_silence_support OR start_cue_support OR end_cue_support
            THEN 'strong' ELSE 'medium' END)
);
CREATE INDEX session_suggestion_stage_idx ON stageflow.session_suggestion(event_id, stage_id, suggestion_id);

CREATE TABLE stageflow.session_suggestion_decision (
    command_id uuid PRIMARY KEY,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    suggestion_id uuid NOT NULL UNIQUE REFERENCES stageflow.session_suggestion(suggestion_id),
    actor_id uuid NOT NULL,
    decided_at timestamptz NOT NULL,
    kind text NOT NULL CHECK (kind IN ('confirmed', 'rejected')),
    reason text,
    session_id uuid REFERENCES stageflow.session(session_id),
    used_start timestamptz,
    used_end timestamptz,
    CHECK ((kind = 'confirmed' AND session_id IS NOT NULL AND used_start IS NOT NULL
            AND used_end IS NOT NULL AND used_end > used_start AND reason IS NULL)
        OR (kind = 'rejected' AND session_id IS NULL AND used_start IS NULL AND used_end IS NULL
            AND reason IS NOT NULL AND length(btrim(reason)) BETWEEN 1 AND 500))
);
CREATE FUNCTION stageflow.session_suggestion_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'session_suggestion_immutable';
END;
$$;
CREATE TRIGGER session_suggestion_run_immutable BEFORE UPDATE OR DELETE ON stageflow.session_suggestion_run
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_immutable();
CREATE TRIGGER session_suggestion_immutable BEFORE UPDATE OR DELETE ON stageflow.session_suggestion
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_immutable();
CREATE TRIGGER session_suggestion_decision_immutable BEFORE UPDATE OR DELETE ON stageflow.session_suggestion_decision
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_immutable();
INSERT INTO stageflow.schema_migration(version) VALUES ('0022_session_suggestions');
