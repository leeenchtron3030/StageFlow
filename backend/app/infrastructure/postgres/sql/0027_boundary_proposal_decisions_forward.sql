CREATE TABLE stageflow.boundary_proposal_decision (
    proposal_id uuid PRIMARY KEY REFERENCES stageflow.session_boundary_proposal(boundary_proposal_id),
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    kind text NOT NULL CHECK (kind IN ('applied', 'dismissed')),
    command_id uuid NOT NULL UNIQUE,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    actor_id uuid NOT NULL,
    decided_at timestamptz NOT NULL,
    reason text CHECK (reason IS NULL OR (length(btrim(reason)) BETWEEN 1 AND 500))
);
CREATE INDEX boundary_proposal_decision_session
    ON stageflow.boundary_proposal_decision(session_id, command_id);

CREATE FUNCTION stageflow.boundary_proposal_decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        RAISE EXCEPTION 'boundary_proposal_decision_immutable';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM stageflow.session_boundary_proposal
                   WHERE boundary_proposal_id=NEW.proposal_id AND session_id=NEW.session_id) THEN
        RAISE EXCEPTION 'boundary_proposal_decision_session_mismatch';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER boundary_proposal_decision_guard
    BEFORE INSERT OR UPDATE OR DELETE ON stageflow.boundary_proposal_decision
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_proposal_decision_guard();

ALTER TABLE stageflow.session_suggestion_run
    ADD COLUMN boundary_proposals_created integer NOT NULL DEFAULT 0
        CHECK (boundary_proposals_created >= 0);

INSERT INTO stageflow.schema_migration(version) VALUES ('0027_boundary_proposal_decisions');
