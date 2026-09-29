-- Widen policy lineage only; retain every v1 constant and immutable row.
ALTER TABLE stageflow.session_suggestion_run
    DROP CONSTRAINT session_suggestion_run_policy_version_check,
    DROP CONSTRAINT session_suggestion_run_policy_constants_check,
    ADD CONSTRAINT session_suggestion_run_policy_version_check CHECK (policy_version IN ('1', '2', '3')),
    ADD CONSTRAINT session_suggestion_run_policy_constants_check CHECK (
        (policy_version = '1' AND policy_constants = '{
    "id": "boundary-suggestion",
    "version": "1",
    "freeze_merge_seconds": 15,
    "changeover_seconds": 30,
    "edge_window_seconds": 1200,
    "minimum_session_seconds": 60,
    "cue_tie_seconds": 60,
    "start_cue_before_seconds": 120,
    "start_cue_after_seconds": 180,
    "end_cue_before_seconds": 180,
    "end_cue_after_seconds": 60,
    "unscheduled_seconds": 120,
    "clock_margin_seconds": 43200
}'::jsonb)
        OR (policy_version = '2' AND policy_constants = '{
    "id": "boundary-suggestion",
    "version": "2",
    "freeze_merge_seconds": 15,
    "changeover_seconds": 60,
    "edge_window_seconds": 1200,
    "minimum_session_seconds": 60,
    "cue_tie_seconds": 60,
    "start_cue_before_seconds": 120,
    "start_cue_after_seconds": 180,
    "end_cue_before_seconds": 180,
    "end_cue_after_seconds": 60,
    "unscheduled_seconds": 120,
    "clock_margin_seconds": 43200,
    "coverage_gap_seconds": 30,
    "strength_cap_seconds": 600,
    "strength_unit_seconds": 60,
    "silence_multiplier": 2,
    "coverage_strength": 30,
    "plan_distance_seconds": 30,
    "cue_bonus": 1,
    "silence_support_share": 0.3
}'::jsonb)
        OR (policy_version = '3' AND policy_constants = '{
    "id": "boundary-suggestion",
    "version": "3",
    "freeze_merge_seconds": 15,
    "changeover_seconds": 60,
    "edge_window_seconds": 1200,
    "minimum_session_seconds": 60,
    "cue_tie_seconds": 60,
    "start_cue_before_seconds": 120,
    "start_cue_after_seconds": 180,
    "end_cue_before_seconds": 180,
    "end_cue_after_seconds": 60,
    "unscheduled_seconds": 120,
    "clock_margin_seconds": 43200,
    "coverage_gap_seconds": 30,
    "strength_cap_seconds": 600,
    "strength_unit_seconds": 60,
    "silence_multiplier": 2,
    "coverage_strength": 30,
    "plan_distance_seconds": 30,
    "cue_bonus": 1,
    "silence_support_share": 0.3,
    "block_gap_seconds": 1200,
    "offset_limit_seconds": 3600,
    "offset_grid_seconds": 60,
    "offset_refine_seconds": 10,
    "offset_support_seconds": 180,
    "offset_penalty_seconds": 600,
    "offset_gate_per_talk": 6
}'::jsonb)
    );
ALTER TABLE stageflow.session_suggestion
    DROP CONSTRAINT session_suggestion_check,
    ADD CONSTRAINT session_suggestion_check CHECK (
        (policy_version = '1' AND suggested_end > suggested_start + interval '60 seconds')
        OR (policy_version IN ('2', '3') AND suggested_end >= suggested_start + interval '60 seconds')
    );

CREATE TABLE stageflow.stage_schedule_offset_setting (
    event_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    command_id uuid NOT NULL UNIQUE,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    set_by uuid NOT NULL,
    set_at timestamptz NOT NULL,
    entry_count integer NOT NULL CHECK (entry_count BETWEEN 0 AND 20),
    PRIMARY KEY (event_id, stage_id, version),
    FOREIGN KEY (stage_id, event_id) REFERENCES stageflow.stage(stage_id, event_id)
);
CREATE TABLE stageflow.stage_schedule_offset_entry (
    event_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    version integer NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 19),
    effective_from timestamptz NOT NULL,
    offset_seconds integer NOT NULL CHECK (offset_seconds BETWEEN -7200 AND 7200),
    PRIMARY KEY (event_id, stage_id, version, ordinal),
    UNIQUE (event_id, stage_id, version, effective_from),
    FOREIGN KEY (event_id, stage_id, version)
        REFERENCES stageflow.stage_schedule_offset_setting(event_id, stage_id, version)
);
CREATE TRIGGER stage_schedule_offset_setting_immutable
    BEFORE UPDATE OR DELETE ON stageflow.stage_schedule_offset_setting
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_immutable();
CREATE TRIGGER stage_schedule_offset_entry_immutable
    BEFORE UPDATE OR DELETE ON stageflow.stage_schedule_offset_entry
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_immutable();

-- The immutable header fixes membership as well as values: later INSERTs cannot
-- append entries to an already committed version. Validate ordering at commit.
CREATE FUNCTION stageflow.schedule_offset_entries_complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected integer; actual integer; last_ordinal integer;
BEGIN
    SELECT entry_count INTO expected FROM stageflow.stage_schedule_offset_setting
        WHERE event_id=NEW.event_id AND stage_id=NEW.stage_id AND version=NEW.version;
    SELECT count(*), max(ordinal) INTO actual, last_ordinal FROM stageflow.stage_schedule_offset_entry
        WHERE event_id=NEW.event_id AND stage_id=NEW.stage_id AND version=NEW.version;
    IF actual <> expected OR (actual > 0 AND last_ordinal <> actual - 1) OR EXISTS (
        SELECT 1 FROM (
            SELECT effective_from, lag(effective_from) OVER (ORDER BY ordinal) AS previous
            FROM stageflow.stage_schedule_offset_entry
            WHERE event_id=NEW.event_id AND stage_id=NEW.stage_id AND version=NEW.version
        ) e WHERE effective_from <= previous
    ) THEN
        RAISE EXCEPTION 'schedule_offset_entries_incomplete_or_unordered';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER schedule_offset_header_complete
    AFTER INSERT ON stageflow.stage_schedule_offset_setting DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.schedule_offset_entries_complete();
CREATE CONSTRAINT TRIGGER schedule_offset_entries_complete
    AFTER INSERT ON stageflow.stage_schedule_offset_entry DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.schedule_offset_entries_complete();

ALTER TABLE stageflow.session_suggestion_run
    ADD COLUMN override_setting_version integer,
    ADD COLUMN block_count integer NOT NULL DEFAULT 0 CHECK (block_count BETWEEN 0 AND 10000),
    ADD CONSTRAINT session_suggestion_run_offset_version_check CHECK (
        policy_version = '3' OR (override_setting_version IS NULL AND block_count = 0)),
    ADD CONSTRAINT session_suggestion_run_offset_setting_fk
        FOREIGN KEY (event_id, stage_id, override_setting_version)
        REFERENCES stageflow.stage_schedule_offset_setting(event_id, stage_id, version);

ALTER TABLE stageflow.session_suggestion
    ADD COLUMN schedule_offset_seconds integer,
    ADD COLUMN schedule_offset_source text,
    ADD CONSTRAINT session_suggestion_offset_check CHECK (
        (policy_version IN ('1', '2') AND schedule_offset_seconds IS NULL AND schedule_offset_source IS NULL)
        OR (policy_version = '3' AND schedule_offset_seconds IS NOT NULL AND schedule_offset_source IS NOT NULL
            AND schedule_offset_seconds BETWEEN -7200 AND 7200
            AND schedule_offset_source IN ('producer', 'estimated', 'none')
            AND (schedule_offset_source <> 'none' OR schedule_offset_seconds = 0)
            AND (schedule_offset_source <> 'estimated' OR schedule_offset_seconds BETWEEN -3600 AND 3600)
            AND (expectation_id IS NOT NULL OR (schedule_offset_seconds = 0 AND schedule_offset_source = 'none')))
    );
CREATE TABLE stageflow.session_suggestion_run_block (
    run_id uuid NOT NULL,
    event_id uuid NOT NULL,
    stage_id uuid NOT NULL,
    policy_id text NOT NULL DEFAULT 'boundary-suggestion' CHECK (policy_id = 'boundary-suggestion'),
    policy_version text NOT NULL DEFAULT '3' CHECK (policy_version = '3'),
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 9999),
    first_planned_start timestamptz NOT NULL,
    last_planned_start timestamptz NOT NULL CHECK (last_planned_start >= first_planned_start),
    talk_count integer NOT NULL CHECK (talk_count BETWEEN 1 AND 10000),
    schedule_offset_seconds integer NOT NULL CHECK (schedule_offset_seconds BETWEEN -7200 AND 7200),
    schedule_offset_source text NOT NULL CHECK (schedule_offset_source IN ('producer', 'estimated', 'none')),
    estimate_score_margin double precision NOT NULL CHECK (estimate_score_margin BETWEEN 0 AND 600000),
    override_setting_version integer,
    PRIMARY KEY (run_id, ordinal),
    FOREIGN KEY (run_id, event_id, stage_id, policy_id, policy_version)
        REFERENCES stageflow.session_suggestion_run(run_id, event_id, stage_id, policy_id, policy_version),
    FOREIGN KEY (event_id, stage_id, override_setting_version)
        REFERENCES stageflow.stage_schedule_offset_setting(event_id, stage_id, version),
    CHECK ((schedule_offset_source = 'producer') = (override_setting_version IS NOT NULL)),
    CHECK (schedule_offset_source <> 'none' OR schedule_offset_seconds = 0),
    CHECK (schedule_offset_source <> 'estimated' OR schedule_offset_seconds BETWEEN -3600 AND 3600)
);
CREATE TRIGGER session_suggestion_run_block_immutable
    BEFORE UPDATE OR DELETE ON stageflow.session_suggestion_run_block
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_immutable();
CREATE FUNCTION stageflow.session_suggestion_blocks_complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE expected integer; actual integer; last_ordinal integer; setting integer;
BEGIN
    SELECT block_count, override_setting_version INTO expected, setting
        FROM stageflow.session_suggestion_run WHERE run_id=NEW.run_id;
    SELECT count(*), max(ordinal) INTO actual, last_ordinal
        FROM stageflow.session_suggestion_run_block WHERE run_id=NEW.run_id;
    IF actual <> expected OR (actual > 0 AND last_ordinal <> actual - 1) OR EXISTS (
        SELECT 1 FROM stageflow.session_suggestion_run_block
        WHERE run_id=NEW.run_id AND override_setting_version IS NOT NULL
            AND override_setting_version IS DISTINCT FROM setting
    ) THEN
        RAISE EXCEPTION 'session_suggestion_blocks_incomplete_or_mismatched';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER session_suggestion_run_blocks_complete
    AFTER INSERT ON stageflow.session_suggestion_run DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_blocks_complete();
CREATE CONSTRAINT TRIGGER session_suggestion_blocks_complete
    AFTER INSERT ON stageflow.session_suggestion_run_block DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.session_suggestion_blocks_complete();
INSERT INTO stageflow.schema_migration(version) VALUES ('0024_session_suggestions_policy_v3');
