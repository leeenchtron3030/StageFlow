DROP TABLE stageflow.editorial_clip;
DROP TABLE stageflow.editorial_moment_review_decision;

DELETE FROM stageflow.schema_migration
WHERE version = '0011_editorial_review_foundation';
