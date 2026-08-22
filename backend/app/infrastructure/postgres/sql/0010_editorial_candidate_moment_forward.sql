CREATE TABLE stageflow.editorial_candidate_moment_location_history (
    location_evaluation_id uuid PRIMARY KEY,
    candidate_moment_id uuid NOT NULL
        REFERENCES stageflow.editorial_candidate_moment(candidate_moment_id),
    evaluated_session_revision bigint NOT NULL
        CHECK (evaluated_session_revision > 0),
    session_authoritative_start timestamptz NOT NULL,
    session_authoritative_end timestamptz,
    location_conflict_reason text CHECK (
        location_conflict_reason IN (
            'partially_excluded_by_session_boundary',
            'excluded_by_session_boundary'
        )
    ),
    evaluated_at timestamptz NOT NULL,
    UNIQUE (candidate_moment_id, evaluated_session_revision),
    CHECK (
        session_authoritative_end IS NULL
        OR session_authoritative_end >= session_authoritative_start
    )
);

CREATE INDEX editorial_candidate_moment_location_current_idx
    ON stageflow.editorial_candidate_moment_location_history (
        candidate_moment_id, evaluated_session_revision DESC, evaluated_at DESC
    );

INSERT INTO stageflow.schema_migration (version)
VALUES ('0010_editorial_candidate_moment');
