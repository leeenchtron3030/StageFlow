-- Widen policy lineage only; retain every v1 constant and immutable row.
ALTER TABLE stageflow.session_suggestion_run
    DROP CONSTRAINT session_suggestion_run_policy_version_check,
    DROP CONSTRAINT session_suggestion_run_policy_constants_check,
    ADD CONSTRAINT session_suggestion_run_policy_version_check CHECK (policy_version IN ('1', '2')),
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
    );
ALTER TABLE stageflow.session_suggestion
    DROP CONSTRAINT session_suggestion_check,
    ADD CONSTRAINT session_suggestion_check CHECK (
        (policy_version = '1' AND suggested_end > suggested_start + interval '60 seconds')
        OR (policy_version = '2' AND suggested_end >= suggested_start + interval '60 seconds')
    );
-- The existing composite FK pins each suggestion to its run's policy identity/version.
INSERT INTO stageflow.schema_migration(version) VALUES ('0023_session_suggestions_policy_v2');
