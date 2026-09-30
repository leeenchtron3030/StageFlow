-- Widen policy lineage only; retain every v1 constant and immutable row.
ALTER TABLE stageflow.session_suggestion_run
    DROP CONSTRAINT session_suggestion_run_policy_version_check,
    DROP CONSTRAINT session_suggestion_run_policy_constants_check,
    ADD CONSTRAINT session_suggestion_run_policy_version_check CHECK (policy_version IN ('1', '2', '3', '4')),
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
        OR (policy_version = '4' AND policy_constants = '{
    "id": "boundary-suggestion",
    "version": "4",
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
    "tau_anchor_seconds": 30,
    "tau_step_seconds": 60,
    "hard_bound_seconds": 5400
}'::jsonb)
    );
ALTER TABLE stageflow.session_suggestion
    DROP CONSTRAINT session_suggestion_check,
    ADD CONSTRAINT session_suggestion_check CHECK (
        (policy_version = '1' AND suggested_end > suggested_start + interval '60 seconds')
        OR (policy_version IN ('2', '3', '4') AND suggested_end >= suggested_start + interval '60 seconds')
    );

ALTER TABLE stageflow.session_suggestion_run
    DROP CONSTRAINT session_suggestion_run_offset_version_check,
    ADD CONSTRAINT session_suggestion_run_offset_version_check CHECK (
        policy_version = '3'
        OR (policy_version = '4' AND block_count = 0)
        OR (policy_version IN ('1', '2') AND override_setting_version IS NULL AND block_count = 0));
ALTER TABLE stageflow.session_suggestion
    DROP CONSTRAINT session_suggestion_offset_check,
    ADD CONSTRAINT session_suggestion_offset_check CHECK (
        (policy_version IN ('1', '2') AND schedule_offset_seconds IS NULL AND schedule_offset_source IS NULL)
        OR (policy_version = '3' AND schedule_offset_seconds IS NOT NULL AND schedule_offset_source IS NOT NULL
            AND schedule_offset_seconds BETWEEN -7200 AND 7200
            AND schedule_offset_source IN ('producer', 'estimated', 'none')
            AND (schedule_offset_source <> 'none' OR schedule_offset_seconds = 0)
            AND (schedule_offset_source <> 'estimated' OR schedule_offset_seconds BETWEEN -3600 AND 3600)
            AND (expectation_id IS NOT NULL OR (schedule_offset_seconds = 0 AND schedule_offset_source = 'none')))
        OR (policy_version = '4' AND schedule_offset_seconds IS NOT NULL AND schedule_offset_source IS NOT NULL
            AND schedule_offset_seconds BETWEEN -7200 AND 7200
            AND schedule_offset_source IN ('producer', 'estimated', 'none')
            AND (schedule_offset_source <> 'none' OR schedule_offset_seconds = 0)
            AND (schedule_offset_source <> 'estimated' OR schedule_offset_seconds BETWEEN -5400 AND 5400)
            AND (expectation_id IS NOT NULL OR (schedule_offset_seconds = 0 AND schedule_offset_source = 'none')))
    );
INSERT INTO stageflow.schema_migration(version) VALUES ('0028_session_suggestions_policy_v4');
