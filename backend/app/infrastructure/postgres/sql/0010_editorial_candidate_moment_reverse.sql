DROP TABLE stageflow.editorial_candidate_moment_location_history;

DELETE FROM stageflow.schema_migration
WHERE version = '0010_editorial_candidate_moment';
