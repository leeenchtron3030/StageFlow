-- Never rewrite v2 lineage or delete advisory history to permit reversal.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.session_suggestion_run WHERE policy_version = '2')
       OR EXISTS (SELECT 1 FROM stageflow.session_suggestion WHERE policy_version = '2') THEN
        RAISE EXCEPTION 'session_suggestion_policy_v2_reverse_requires_empty_tables_for_v2';
    END IF;
END;
$$;
ALTER TABLE stageflow.session_suggestion
    DROP CONSTRAINT session_suggestion_check,
    ADD CONSTRAINT session_suggestion_check
        CHECK (suggested_end > suggested_start + interval '60 seconds');
ALTER TABLE stageflow.session_suggestion_run
    DROP CONSTRAINT session_suggestion_run_policy_version_check,
    DROP CONSTRAINT session_suggestion_run_policy_constants_check,
    ADD CONSTRAINT session_suggestion_run_policy_version_check CHECK (policy_version = '1'),
    ADD CONSTRAINT session_suggestion_run_policy_constants_check CHECK (policy_constants = '{
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
}'::jsonb);
DELETE FROM stageflow.schema_migration WHERE version = '0023_session_suggestions_policy_v2';
