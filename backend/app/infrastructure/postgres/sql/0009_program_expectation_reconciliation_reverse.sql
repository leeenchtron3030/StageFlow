DROP TABLE stageflow.program_expectation_sync_snapshot;

ALTER TABLE stageflow.program_expectation_revision
    DROP CONSTRAINT program_expectation_revision_lifecycle_state_check,
    DROP COLUMN lifecycle_changed_at,
    DROP COLUMN last_observed_at,
    DROP COLUMN synchronization_scope,
    DROP COLUMN lifecycle_state;

ALTER TABLE stageflow.program_expectation
    DROP CONSTRAINT program_expectation_lifecycle_state_check,
    DROP COLUMN lifecycle_changed_at,
    DROP COLUMN last_observed_at,
    DROP COLUMN synchronization_scope,
    DROP COLUMN lifecycle_state;

DELETE FROM stageflow.schema_migration
WHERE version = '0009_program_expectation_reconciliation';
