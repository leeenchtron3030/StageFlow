ALTER TABLE stageflow.session_suggestion_run
    ADD COLUMN already_realized integer NOT NULL DEFAULT 0 CHECK (already_realized >= 0);

INSERT INTO stageflow.schema_migration(version)
    VALUES ('0026_session_suggestions_already_realized');
