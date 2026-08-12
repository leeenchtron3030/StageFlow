DELETE FROM stageflow.session_completion_asset
WHERE snapshot_origin = 'legacy_reconstructed_0005';

ALTER TABLE stageflow.session_completion_asset
    DROP CONSTRAINT IF EXISTS session_completion_asset_snapshot_origin_ck,
    DROP COLUMN IF EXISTS snapshot_origin;

ALTER TABLE stageflow.session_completion_history
    DROP CONSTRAINT IF EXISTS session_completion_history_snapshot_reason_ck,
    DROP CONSTRAINT IF EXISTS session_completion_history_snapshot_status_ck,
    DROP COLUMN IF EXISTS membership_snapshot_reason,
    DROP COLUMN IF EXISTS membership_snapshot_status;

ALTER TABLE stageflow.human_command_idempotency
    DROP CONSTRAINT IF EXISTS human_command_idempotency_result_snapshot_ck,
    DROP COLUMN IF EXISTS result_snapshot;

DELETE FROM stageflow.schema_migration
WHERE version = '0005_kernel_follow_up_closure';
