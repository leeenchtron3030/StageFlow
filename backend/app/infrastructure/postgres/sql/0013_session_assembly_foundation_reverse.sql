DROP TABLE stageflow.assembly_approval_decision;
DROP TABLE stageflow.assembly_metadata_snapshot;
DROP TABLE stageflow.assembly_binding;
DROP TABLE stageflow.assembly_member;
DROP TABLE stageflow.assembly_revision;
DROP TABLE stageflow.assembly_template;
DROP TABLE stageflow.assembly_command;
DROP FUNCTION stageflow.assembly_history_is_immutable();
DELETE FROM stageflow.schema_migration WHERE version = '0013_session_assembly_foundation';
