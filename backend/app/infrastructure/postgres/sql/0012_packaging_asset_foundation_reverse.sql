DROP TABLE stageflow.packaging_asset_approval_decision;
DROP TABLE stageflow.packaging_asset_revision;
DROP TABLE stageflow.packaging_asset;
DROP FUNCTION stageflow.packaging_asset_history_is_immutable();
DROP TABLE IF EXISTS stageflow.packaging_asset_command;
DELETE FROM stageflow.schema_migration WHERE version = '0012_packaging_asset_foundation';
