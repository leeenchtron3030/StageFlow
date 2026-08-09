DROP INDEX IF EXISTS stageflow.session_boundary_proposal_session_time;
DROP TABLE IF EXISTS stageflow.session_boundary_proposal;
DELETE FROM stageflow.schema_migration WHERE version = '0003_kernel_projections';
