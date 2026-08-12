ALTER TABLE stageflow.human_command_idempotency
    ADD COLUMN IF NOT EXISTS result_snapshot jsonb;

ALTER TABLE stageflow.human_command_idempotency
    ADD CONSTRAINT human_command_idempotency_result_snapshot_ck
    CHECK (result_snapshot IS NULL OR jsonb_typeof(result_snapshot) = 'object');

ALTER TABLE stageflow.session_completion_history
    ADD COLUMN IF NOT EXISTS membership_snapshot_status text NOT NULL DEFAULT 'recorded',
    ADD COLUMN IF NOT EXISTS membership_snapshot_reason text;

ALTER TABLE stageflow.session_completion_history
    ADD CONSTRAINT session_completion_history_snapshot_status_ck
    CHECK (membership_snapshot_status IN ('recorded', 'reconstructed', 'unresolved')),
    ADD CONSTRAINT session_completion_history_snapshot_reason_ck
    CHECK (
        (membership_snapshot_status = 'recorded' AND membership_snapshot_reason IS NULL)
        OR
        (membership_snapshot_status <> 'recorded'
         AND membership_snapshot_reason IS NOT NULL
         AND btrim(membership_snapshot_reason) <> '')
    );

ALTER TABLE stageflow.session_completion_asset
    ADD COLUMN IF NOT EXISTS snapshot_origin text NOT NULL DEFAULT 'recorded';

ALTER TABLE stageflow.session_completion_asset
    ADD CONSTRAINT session_completion_asset_snapshot_origin_ck
    CHECK (snapshot_origin IN ('recorded', 'legacy_reconstructed_0005'));

UPDATE stageflow.session_completion_history c
SET membership_snapshot_status = CASE
        WHEN EXISTS (
            SELECT 1
            FROM stageflow.media_association_history h
            JOIN stageflow.completed_media_asset_registry a ON a.asset_id = h.asset_id
            JOIN stageflow.session s ON s.session_id = c.session_id
            WHERE a.stage_id = s.stage_id
              AND h.decided_at = c.decided_at
        ) THEN 'unresolved'
        ELSE 'reconstructed'
    END,
    membership_snapshot_reason = CASE
        WHEN EXISTS (
            SELECT 1
            FROM stageflow.media_association_history h
            JOIN stageflow.completed_media_asset_registry a ON a.asset_id = h.asset_id
            JOIN stageflow.session s ON s.session_id = c.session_id
            WHERE a.stage_id = s.stage_id
              AND h.decided_at = c.decided_at
        ) THEN 'legacy_equal_time_association_ambiguity'
        ELSE 'legacy_strictly_prior_association_history'
    END
FROM stageflow.human_command_idempotency command, stageflow.session current_session
WHERE command.operation_id = c.operation_id
  AND command.command_kind = 'legacy_package_completion'
  AND current_session.session_id = c.session_id
  AND c.approved
  AND (
      current_session.package_state <> 'complete'
      OR current_session.package_revision <> c.package_revision
  )
  AND NOT EXISTS (
      SELECT 1 FROM stageflow.session_completion_asset membership
      WHERE membership.completion_decision_id = c.completion_decision_id
  );

INSERT INTO stageflow.session_completion_asset (
    completion_decision_id, session_id, package_revision,
    asset_id, association_revision, snapshot_origin
)
SELECT c.completion_decision_id, c.session_id, c.package_revision,
       latest.asset_id, latest.association_revision, 'legacy_reconstructed_0005'
FROM stageflow.session_completion_history c
JOIN stageflow.session s ON s.session_id = c.session_id
JOIN LATERAL (
    SELECT DISTINCT ON (h.asset_id)
           h.asset_id, h.association_revision, h.association_status, h.session_id
    FROM stageflow.media_association_history h
    JOIN stageflow.completed_media_asset_registry a ON a.asset_id = h.asset_id
    WHERE a.stage_id = s.stage_id
      AND h.decided_at < c.decided_at
    ORDER BY h.asset_id, h.decided_at DESC, h.association_revision DESC
) latest
  ON latest.association_status = 'associated'
 AND latest.session_id = c.session_id
WHERE c.membership_snapshot_status = 'reconstructed'
ON CONFLICT (completion_decision_id, asset_id) DO NOTHING;

INSERT INTO stageflow.schema_migration (version)
VALUES ('0005_kernel_follow_up_closure')
ON CONFLICT (version) DO NOTHING;
