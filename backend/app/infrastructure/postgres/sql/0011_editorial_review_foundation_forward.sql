CREATE TABLE stageflow.editorial_moment_review_decision (
    review_decision_id uuid PRIMARY KEY,
    decision_sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    operation_id uuid NOT NULL UNIQUE,
    request_digest char(64) NOT NULL
        CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    candidate_moment_id uuid NOT NULL
        REFERENCES stageflow.editorial_candidate_moment(candidate_moment_id),
    candidate_revision bigint NOT NULL CHECK (candidate_revision > 0),
    actor_id uuid NOT NULL,
    action text NOT NULL CHECK (
        action IN (
            'approve_and_create_clip',
            'reject',
            'revise_range',
            'defer'
        )
    ),
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    notes text CHECK (notes IS NULL OR btrim(notes) <> ''),
    adjusted_timeline_start_microseconds bigint
        CHECK (adjusted_timeline_start_microseconds >= 0),
    adjusted_timeline_end_microseconds bigint,
    decided_at timestamptz NOT NULL,
    UNIQUE (
        review_decision_id,
        candidate_moment_id,
        candidate_revision
    ),
    CHECK (
        (
            adjusted_timeline_start_microseconds IS NULL
            AND adjusted_timeline_end_microseconds IS NULL
        )
        OR (
            adjusted_timeline_start_microseconds IS NOT NULL
            AND adjusted_timeline_end_microseconds IS NOT NULL
            AND adjusted_timeline_end_microseconds
                >= adjusted_timeline_start_microseconds
        )
    ),
    CHECK (
        (
            action = 'revise_range'
            AND adjusted_timeline_start_microseconds IS NOT NULL
        )
        OR (
            action = 'approve_and_create_clip'
        )
        OR (
            action IN ('reject', 'defer')
            AND adjusted_timeline_start_microseconds IS NULL
        )
    )
);

CREATE INDEX editorial_moment_review_candidate_history_idx
    ON stageflow.editorial_moment_review_decision (
        candidate_moment_id,
        decision_sequence
    );

CREATE TABLE stageflow.editorial_clip (
    clip_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    candidate_moment_id uuid NOT NULL,
    candidate_revision bigint NOT NULL CHECK (candidate_revision > 0),
    review_decision_id uuid NOT NULL UNIQUE,
    timeline_start_microseconds bigint NOT NULL
        CHECK (timeline_start_microseconds >= 0),
    timeline_end_microseconds bigint NOT NULL,
    created_at timestamptz NOT NULL,
    revision bigint NOT NULL CHECK (revision = 1),
    FOREIGN KEY (
        review_decision_id,
        candidate_moment_id,
        candidate_revision
    ) REFERENCES stageflow.editorial_moment_review_decision (
        review_decision_id,
        candidate_moment_id,
        candidate_revision
    ),
    CHECK (timeline_end_microseconds >= timeline_start_microseconds)
);

CREATE INDEX editorial_clip_candidate_history_idx
    ON stageflow.editorial_clip (
        candidate_moment_id,
        created_at,
        clip_id
    );

INSERT INTO stageflow.schema_migration (version)
VALUES ('0011_editorial_review_foundation');
