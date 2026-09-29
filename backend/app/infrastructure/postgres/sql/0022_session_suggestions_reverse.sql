DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.session_suggestion_run)
       OR EXISTS (SELECT 1 FROM stageflow.session_suggestion)
       OR EXISTS (SELECT 1 FROM stageflow.session_suggestion_decision) THEN
        RAISE EXCEPTION 'session_suggestion_reverse_requires_empty_tables';
    END IF;
END;
$$;
DROP TABLE stageflow.session_suggestion_decision;
DROP TABLE stageflow.session_suggestion;
DROP TABLE stageflow.session_suggestion_run;
DROP FUNCTION stageflow.session_suggestion_immutable();
DELETE FROM stageflow.schema_migration WHERE version = '0022_session_suggestions';
