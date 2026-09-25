DROP TABLE stageflow.assembly_metadata_override_snapshot;
DROP TABLE stageflow.assembly_metadata_override;
DELETE FROM stageflow.schema_migration WHERE version = '0014_assembly_metadata_overrides';
