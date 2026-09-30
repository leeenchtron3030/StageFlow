LOCK TABLE stageflow.boundary_proposal_decision IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.boundary_proposal_decision) THEN
        RAISE EXCEPTION 'boundary_proposal_reverse_requires_empty_decisions';
    END IF;
END;
$$;
DROP TABLE stageflow.boundary_proposal_decision;
DROP FUNCTION stageflow.boundary_proposal_decision_guard();
ALTER TABLE stageflow.session_suggestion_run DROP COLUMN boundary_proposals_created;
DELETE FROM stageflow.schema_migration WHERE version='0027_boundary_proposal_decisions';
