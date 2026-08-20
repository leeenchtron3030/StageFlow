ALTER TABLE stageflow.program_expectation
    ADD COLUMN lifecycle_state text NOT NULL DEFAULT 'current',
    ADD COLUMN synchronization_scope text,
    ADD COLUMN last_observed_at timestamptz,
    ADD COLUMN lifecycle_changed_at timestamptz,
    ADD CONSTRAINT program_expectation_lifecycle_state_check
        CHECK (lifecycle_state IN ('current', 'withdrawn'));

UPDATE stageflow.program_expectation
SET synchronization_scope = concat(
        'devcon:', external_references->>'devcon_event_id', ':',
        external_references->>'devcon_room_id'
    )
WHERE external_references->>'provider' = 'devcon'
  AND btrim(coalesce(external_references->>'devcon_event_id', '')) <> ''
  AND btrim(coalesce(external_references->>'devcon_room_id', '')) <> '';

UPDATE stageflow.program_expectation
SET last_observed_at = recorded_at,
    lifecycle_changed_at = recorded_at;

ALTER TABLE stageflow.program_expectation
    ALTER COLUMN last_observed_at SET NOT NULL,
    ALTER COLUMN lifecycle_changed_at SET NOT NULL;

ALTER TABLE stageflow.program_expectation_revision
    ADD COLUMN lifecycle_state text NOT NULL DEFAULT 'current',
    ADD COLUMN synchronization_scope text,
    ADD COLUMN last_observed_at timestamptz,
    ADD COLUMN lifecycle_changed_at timestamptz,
    ADD CONSTRAINT program_expectation_revision_lifecycle_state_check
        CHECK (lifecycle_state IN ('current', 'withdrawn'));

UPDATE stageflow.program_expectation_revision revision
SET synchronization_scope = expectation.synchronization_scope,
    last_observed_at = revision.recorded_at,
    lifecycle_changed_at = revision.recorded_at
FROM stageflow.program_expectation expectation
WHERE expectation.expectation_id = revision.expectation_id;

ALTER TABLE stageflow.program_expectation_revision
    ALTER COLUMN last_observed_at SET NOT NULL,
    ALTER COLUMN lifecycle_changed_at SET NOT NULL;

CREATE TABLE stageflow.program_expectation_sync_snapshot (
    synchronization_scope text NOT NULL CHECK (btrim(synchronization_scope) <> ''),
    event_id uuid NOT NULL,
    expected_stage_id uuid NOT NULL,
    provider text NOT NULL CHECK (btrim(provider) <> ''),
    synchronized_at timestamptz NOT NULL,
    observed bigint NOT NULL CHECK (observed >= 0),
    added bigint NOT NULL CHECK (added >= 0),
    changed bigint NOT NULL CHECK (changed >= 0),
    unchanged bigint NOT NULL CHECK (unchanged >= 0),
    withdrawn bigint NOT NULL CHECK (withdrawn >= 0),
    restored bigint NOT NULL CHECK (restored >= 0),
    change_summary jsonb NOT NULL DEFAULT '[]'::jsonb,
    changes_truncated boolean NOT NULL DEFAULT false,
    PRIMARY KEY (event_id, expected_stage_id, synchronization_scope),
    FOREIGN KEY (expected_stage_id, event_id)
        REFERENCES stageflow.stage(stage_id, event_id),
    CHECK (added + changed + unchanged + restored = observed)
);

INSERT INTO stageflow.schema_migration (version)
VALUES ('0009_program_expectation_reconciliation');
