DROP TABLE IF EXISTS stageflow.session_completion_asset;

ALTER TABLE stageflow.session_completion_history
    DROP CONSTRAINT IF EXISTS session_completion_history_membership_uk,
    DROP CONSTRAINT IF EXISTS session_completion_history_reason_ck,
    DROP CONSTRAINT IF EXISTS session_completion_history_operation_fk,
    DROP COLUMN IF EXISTS operation_id;

ALTER TABLE stageflow.media_association_history
    DROP CONSTRAINT IF EXISTS media_association_history_membership_uk,
    DROP CONSTRAINT IF EXISTS media_association_history_operation_fk,
    DROP CONSTRAINT IF EXISTS media_association_history_session_fk,
    DROP CONSTRAINT IF EXISTS media_association_history_policy_authority_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_input_references_array_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_evidence_ids_array_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_reason_codes_array_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_actor_operation_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_shape_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_authority_ck,
    DROP CONSTRAINT IF EXISTS media_association_history_status_ck,
    DROP COLUMN IF EXISTS operation_id,
    DROP COLUMN IF EXISTS input_references,
    DROP COLUMN IF EXISTS policy_version,
    DROP COLUMN IF EXISTS policy_id;

ALTER TABLE stageflow.media_association
    DROP CONSTRAINT IF EXISTS media_association_operation_fk,
    DROP CONSTRAINT IF EXISTS media_association_operation_authority_ck,
    DROP CONSTRAINT IF EXISTS media_association_policy_authority_ck,
    DROP CONSTRAINT IF EXISTS media_association_input_references_array_ck,
    DROP CONSTRAINT IF EXISTS media_association_evidence_ids_array_ck,
    DROP CONSTRAINT IF EXISTS media_association_reason_codes_array_ck,
    DROP COLUMN IF EXISTS operation_id,
    DROP COLUMN IF EXISTS input_references,
    DROP COLUMN IF EXISTS policy_version,
    DROP COLUMN IF EXISTS policy_id;

ALTER TABLE stageflow.session_boundary_history
    DROP CONSTRAINT IF EXISTS session_boundary_history_reason_ck,
    DROP CONSTRAINT IF EXISTS session_boundary_history_declared_actor_ck,
    DROP CONSTRAINT IF EXISTS session_boundary_history_operation_fk,
    DROP COLUMN IF EXISTS operation_id;

DROP TABLE IF EXISTS stageflow.human_command_idempotency;

DELETE FROM stageflow.schema_migration
WHERE version = '0004_kernel_review_corrections';
