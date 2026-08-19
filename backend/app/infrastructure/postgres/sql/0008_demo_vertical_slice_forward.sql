ALTER TABLE stageflow.human_command_idempotency
    DROP CONSTRAINT human_command_idempotency_command_kind_check;

ALTER TABLE stageflow.human_command_idempotency
    ADD CONSTRAINT human_command_idempotency_command_kind_check
    CHECK (
        command_kind IN (
            'session_start', 'session_boundary_correction', 'media_assignment',
            'package_ready', 'package_completion', 'editorial_moment_declaration',
            'legacy_boundary', 'legacy_media_assignment', 'legacy_package_completion'
        )
    );

CREATE TABLE stageflow.session_package_ready_history (
    package_ready_decision_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    package_revision bigint NOT NULL CHECK (package_revision > 0),
    actor_id uuid NOT NULL,
    reason text NOT NULL CHECK (btrim(reason) <> ''),
    decided_at timestamptz NOT NULL,
    operation_id uuid NOT NULL UNIQUE
        REFERENCES stageflow.human_command_idempotency(operation_id),
    resulting_session_revision bigint NOT NULL CHECK (resulting_session_revision > 0),
    UNIQUE (package_ready_decision_id, session_id, package_revision)
);

CREATE TABLE stageflow.editorial_candidate_moment (
    candidate_moment_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    expected_session_revision bigint NOT NULL CHECK (expected_session_revision > 0),
    timeline_start_microseconds bigint NOT NULL CHECK (timeline_start_microseconds >= 0),
    timeline_end_microseconds bigint,
    session_authoritative_start timestamptz NOT NULL,
    session_authoritative_end timestamptz,
    origin text NOT NULL CHECK (origin = 'declared'),
    epistemic_kind text NOT NULL CHECK (epistemic_kind = 'declared'),
    reason_code text NOT NULL CHECK (reason_code = 'human_mark_moment'),
    actor_id uuid NOT NULL,
    operation_id uuid NOT NULL UNIQUE
        REFERENCES stageflow.human_command_idempotency(operation_id),
    note text,
    declared_at timestamptz NOT NULL,
    revision bigint NOT NULL CHECK (revision = 1),
    CHECK (
        timeline_end_microseconds IS NULL
        OR timeline_end_microseconds >= timeline_start_microseconds
    ),
    CHECK (note IS NULL OR btrim(note) <> ''),
    CHECK (
        session_authoritative_end IS NULL
        OR session_authoritative_end >= session_authoritative_start
    )
);

CREATE INDEX editorial_candidate_moment_session_timeline_idx
    ON stageflow.editorial_candidate_moment(
        session_id, timeline_start_microseconds, candidate_moment_id
    );

INSERT INTO stageflow.schema_migration (version)
VALUES ('0008_demo_vertical_slice');
