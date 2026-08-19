DROP TABLE stageflow.editorial_candidate_moment;
DROP TABLE stageflow.session_package_ready_history;

DELETE FROM stageflow.human_command_idempotency
WHERE command_kind IN ('package_ready', 'editorial_moment_declaration');

ALTER TABLE stageflow.human_command_idempotency
    DROP CONSTRAINT human_command_idempotency_command_kind_check;

ALTER TABLE stageflow.human_command_idempotency
    ADD CONSTRAINT human_command_idempotency_command_kind_check
    CHECK (
        command_kind IN (
            'session_start', 'session_boundary_correction', 'media_assignment',
            'package_completion', 'legacy_boundary',
            'legacy_media_assignment', 'legacy_package_completion'
        )
    );

DELETE FROM stageflow.schema_migration
WHERE version = '0008_demo_vertical_slice';
