ALTER TABLE stageflow.session_suggestion_run DROP COLUMN already_realized;

DELETE FROM stageflow.schema_migration
    WHERE version = '0026_session_suggestions_already_realized';
