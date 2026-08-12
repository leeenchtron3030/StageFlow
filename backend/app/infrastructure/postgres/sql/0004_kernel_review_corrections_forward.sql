CREATE TABLE IF NOT EXISTS stageflow.human_command_idempotency (
    operation_id uuid PRIMARY KEY,
    command_kind text NOT NULL CHECK (
        command_kind IN (
            'session_start', 'session_boundary_correction', 'media_assignment',
            'package_completion', 'legacy_boundary',
            'legacy_media_assignment', 'legacy_package_completion'
        )
    ),
    request_digest text NOT NULL CHECK (length(request_digest) = 64),
    result_id uuid NOT NULL,
    recorded_at timestamptz NOT NULL
);

ALTER TABLE stageflow.media_association
    ADD COLUMN IF NOT EXISTS policy_id text,
    ADD COLUMN IF NOT EXISTS policy_version text,
    ADD COLUMN IF NOT EXISTS input_references jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS operation_id uuid;

ALTER TABLE stageflow.media_association_history
    ADD COLUMN IF NOT EXISTS policy_id text,
    ADD COLUMN IF NOT EXISTS policy_version text,
    ADD COLUMN IF NOT EXISTS input_references jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS operation_id uuid;

ALTER TABLE stageflow.session_boundary_history
    ADD COLUMN IF NOT EXISTS operation_id uuid;

ALTER TABLE stageflow.session_completion_history
    ADD COLUMN IF NOT EXISTS operation_id uuid;

UPDATE stageflow.media_association
SET policy_id = 'stageflow.kernel.media-association', policy_version = '1.0.0'
WHERE authority = 'deterministic' AND policy_id IS NULL;

UPDATE stageflow.media_association_history
SET policy_id = 'stageflow.kernel.media-association', policy_version = '1.0.0'
WHERE authority = 'deterministic' AND policy_id IS NULL;

UPDATE stageflow.media_association a
SET input_references = jsonb_build_array(
        jsonb_build_object(
            'record_type', 'registered_media_asset',
            'record_id', a.asset_id::text,
            'revision', NULL
        ),
        jsonb_build_object(
            'record_type', 'media_candidate',
            'record_id', r.candidate_id::text,
            'revision', NULL
        ),
        jsonb_build_object(
            'record_type', 'stage_source_binding',
            'record_id', r.source_binding_key,
            'revision', NULL
        )
    ) || CASE
        WHEN a.session_id IS NULL THEN '[]'::jsonb
        ELSE jsonb_build_array(jsonb_build_object(
            'record_type', 'session',
            'record_id', a.session_id::text,
            'revision', NULL
        ))
    END
FROM stageflow.completed_media_asset_registry r
WHERE r.asset_id = a.asset_id
  AND jsonb_array_length(a.input_references) = 0;

UPDATE stageflow.media_association_history h
SET input_references = jsonb_build_array(
        jsonb_build_object(
            'record_type', 'registered_media_asset',
            'record_id', h.asset_id::text,
            'revision', NULL
        ),
        jsonb_build_object(
            'record_type', 'media_candidate',
            'record_id', r.candidate_id::text,
            'revision', NULL
        ),
        jsonb_build_object(
            'record_type', 'stage_source_binding',
            'record_id', r.source_binding_key,
            'revision', NULL
        )
    ) || CASE
        WHEN h.session_id IS NULL THEN '[]'::jsonb
        ELSE jsonb_build_array(jsonb_build_object(
            'record_type', 'session',
            'record_id', h.session_id::text,
            'revision', NULL
        ))
    END
FROM stageflow.completed_media_asset_registry r
WHERE r.asset_id = h.asset_id
  AND jsonb_array_length(h.input_references) = 0;

INSERT INTO stageflow.human_command_idempotency (
    operation_id, command_kind, request_digest, result_id, recorded_at
)
SELECT operation_id, 'session_start', request_digest, session_id, applied_at
FROM stageflow.session_start_operation
ON CONFLICT (operation_id) DO NOTHING;

UPDATE stageflow.session_boundary_history b
SET operation_id = o.operation_id
FROM stageflow.session_start_operation o
WHERE b.session_id = o.session_id
  AND b.reason = 'human_session_start'
  AND b.operation_id IS NULL;

INSERT INTO stageflow.human_command_idempotency (
    operation_id, command_kind, request_digest, result_id, recorded_at
)
SELECT boundary_decision_id, 'legacy_boundary',
       md5(boundary_decision_id::text) || md5('boundary:' || boundary_decision_id::text),
       boundary_decision_id, decided_at
FROM stageflow.session_boundary_history
WHERE operation_id IS NULL
ON CONFLICT (operation_id) DO NOTHING;

UPDATE stageflow.session_boundary_history
SET operation_id = boundary_decision_id
WHERE operation_id IS NULL;

INSERT INTO stageflow.human_command_idempotency (
    operation_id, command_kind, request_digest, result_id, recorded_at
)
SELECT association_history_id, 'legacy_media_assignment',
       md5(association_history_id::text) || md5('association:' || association_history_id::text),
       association_history_id, decided_at
FROM stageflow.media_association_history
WHERE authority = 'human' AND operation_id IS NULL
ON CONFLICT (operation_id) DO NOTHING;

UPDATE stageflow.media_association_history
SET operation_id = association_history_id
WHERE authority = 'human' AND operation_id IS NULL;

UPDATE stageflow.media_association a
SET operation_id = h.operation_id
FROM stageflow.media_association_history h
WHERE h.asset_id = a.asset_id
  AND h.association_revision = a.revision
  AND a.authority = 'human';

INSERT INTO stageflow.human_command_idempotency (
    operation_id, command_kind, request_digest, result_id, recorded_at
)
SELECT completion_decision_id, 'legacy_package_completion',
       md5(completion_decision_id::text) || md5('completion:' || completion_decision_id::text),
       completion_decision_id, decided_at
FROM stageflow.session_completion_history
WHERE operation_id IS NULL
ON CONFLICT (operation_id) DO NOTHING;

UPDATE stageflow.session_completion_history
SET operation_id = completion_decision_id
WHERE operation_id IS NULL;

ALTER TABLE stageflow.session_boundary_history
    ALTER COLUMN operation_id SET NOT NULL;

ALTER TABLE stageflow.session_completion_history
    ALTER COLUMN operation_id SET NOT NULL;

ALTER TABLE stageflow.session_boundary_history
    ADD CONSTRAINT session_boundary_history_operation_fk
    FOREIGN KEY (operation_id)
    REFERENCES stageflow.human_command_idempotency(operation_id),
    ADD CONSTRAINT session_boundary_history_declared_actor_ck
    CHECK (epistemic_kind <> 'declared' OR actor_id IS NOT NULL),
    ADD CONSTRAINT session_boundary_history_reason_ck
    CHECK (btrim(reason) <> '');

ALTER TABLE stageflow.media_association
    ADD CONSTRAINT media_association_reason_codes_array_ck
    CHECK (jsonb_typeof(reason_codes) = 'array' AND jsonb_array_length(reason_codes) > 0),
    ADD CONSTRAINT media_association_evidence_ids_array_ck
    CHECK (jsonb_typeof(evidence_ids) = 'array'),
    ADD CONSTRAINT media_association_input_references_array_ck
    CHECK (
        jsonb_typeof(input_references) = 'array'
        AND jsonb_array_length(input_references) > 0
    ),
    ADD CONSTRAINT media_association_policy_authority_ck
    CHECK (
        (authority = 'deterministic'
         AND policy_id IS NOT NULL AND policy_version IS NOT NULL
         AND btrim(policy_id) <> '' AND btrim(policy_version) <> '')
        OR (authority = 'human' AND policy_id IS NULL AND policy_version IS NULL)
    ),
    ADD CONSTRAINT media_association_operation_authority_ck
    CHECK (
        (authority = 'human' AND operation_id IS NOT NULL)
        OR (authority = 'deterministic' AND operation_id IS NULL)
    ),
    ADD CONSTRAINT media_association_operation_fk
    FOREIGN KEY (operation_id)
    REFERENCES stageflow.human_command_idempotency(operation_id);

ALTER TABLE stageflow.media_association_history
    ADD CONSTRAINT media_association_history_status_ck
    CHECK (association_status IN ('associated', 'unresolved', 'conflict')),
    ADD CONSTRAINT media_association_history_authority_ck
    CHECK (authority IN ('deterministic', 'human')),
    ADD CONSTRAINT media_association_history_shape_ck
    CHECK (
        (association_status = 'associated' AND session_id IS NOT NULL)
        OR (association_status <> 'associated' AND session_id IS NULL)
    ),
    ADD CONSTRAINT media_association_history_actor_operation_ck
    CHECK (
        (authority = 'human' AND actor_id IS NOT NULL AND operation_id IS NOT NULL)
        OR (authority = 'deterministic' AND operation_id IS NULL)
    ),
    ADD CONSTRAINT media_association_history_reason_codes_array_ck
    CHECK (jsonb_typeof(reason_codes) = 'array' AND jsonb_array_length(reason_codes) > 0),
    ADD CONSTRAINT media_association_history_evidence_ids_array_ck
    CHECK (jsonb_typeof(evidence_ids) = 'array'),
    ADD CONSTRAINT media_association_history_input_references_array_ck
    CHECK (
        jsonb_typeof(input_references) = 'array'
        AND jsonb_array_length(input_references) > 0
    ),
    ADD CONSTRAINT media_association_history_policy_authority_ck
    CHECK (
        (authority = 'deterministic'
         AND policy_id IS NOT NULL AND policy_version IS NOT NULL
         AND btrim(policy_id) <> '' AND btrim(policy_version) <> '')
        OR (authority = 'human' AND policy_id IS NULL AND policy_version IS NULL)
    ),
    ADD CONSTRAINT media_association_history_session_fk
    FOREIGN KEY (session_id) REFERENCES stageflow.session(session_id),
    ADD CONSTRAINT media_association_history_operation_fk
    FOREIGN KEY (operation_id)
    REFERENCES stageflow.human_command_idempotency(operation_id),
    ADD CONSTRAINT media_association_history_membership_uk
    UNIQUE (asset_id, association_revision, session_id);

ALTER TABLE stageflow.session_completion_history
    ADD CONSTRAINT session_completion_history_operation_fk
    FOREIGN KEY (operation_id)
    REFERENCES stageflow.human_command_idempotency(operation_id),
    ADD CONSTRAINT session_completion_history_reason_ck
    CHECK (btrim(reason) <> ''),
    ADD CONSTRAINT session_completion_history_membership_uk
    UNIQUE (completion_decision_id, session_id, package_revision);

CREATE TABLE IF NOT EXISTS stageflow.session_completion_asset (
    completion_decision_id uuid NOT NULL,
    session_id uuid NOT NULL,
    package_revision bigint NOT NULL CHECK (package_revision > 0),
    asset_id uuid NOT NULL,
    association_revision bigint NOT NULL CHECK (association_revision > 0),
    PRIMARY KEY (completion_decision_id, asset_id),
    FOREIGN KEY (completion_decision_id, session_id, package_revision)
        REFERENCES stageflow.session_completion_history(
            completion_decision_id, session_id, package_revision
        ),
    FOREIGN KEY (asset_id, association_revision, session_id)
        REFERENCES stageflow.media_association_history(
            asset_id, association_revision, session_id
    )
);

INSERT INTO stageflow.session_completion_asset (
    completion_decision_id, session_id, package_revision,
    asset_id, association_revision
)
SELECT c.completion_decision_id, c.session_id, c.package_revision,
       a.asset_id, a.revision
FROM stageflow.session_completion_history c
JOIN stageflow.session s
  ON s.session_id = c.session_id
 AND s.package_state = 'complete'
 AND s.package_revision = c.package_revision
JOIN stageflow.media_association a
  ON a.session_id = c.session_id
 AND a.association_status = 'associated'
WHERE c.approved
ON CONFLICT (completion_decision_id, asset_id) DO NOTHING;

INSERT INTO stageflow.schema_migration (version)
VALUES ('0004_kernel_review_corrections')
ON CONFLICT (version) DO NOTHING;
