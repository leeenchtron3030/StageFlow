CREATE TABLE IF NOT EXISTS stageflow.session_boundary_proposal (
    boundary_proposal_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    boundary_kind text NOT NULL CHECK (boundary_kind IN ('start', 'end')),
    boundary_at timestamptz NOT NULL,
    epistemic_kind text NOT NULL CHECK (
        epistemic_kind IN ('observed', 'derived', 'inferred')
    ),
    proposer_id uuid NOT NULL,
    evidence_ids jsonb NOT NULL,
    policy_id text NOT NULL CHECK (btrim(policy_id) <> ''),
    policy_version text NOT NULL CHECK (btrim(policy_version) <> ''),
    model_id text,
    model_version text,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    proposed_at timestamptz NOT NULL,
    CHECK ((model_id IS NULL) = (model_version IS NULL))
);

CREATE INDEX IF NOT EXISTS session_boundary_proposal_session_time
ON stageflow.session_boundary_proposal(session_id, proposed_at DESC);

INSERT INTO stageflow.schema_migration (version)
VALUES ('0003_kernel_projections')
ON CONFLICT (version) DO NOTHING;
