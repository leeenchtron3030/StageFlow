-- Add advisory ordering provenance without updating or backfilling immutable members.
ALTER TABLE stageflow.assembly_member
    DROP CONSTRAINT assembly_member_order_source_check,
    ADD CONSTRAINT assembly_member_order_source_check
        CHECK (order_source IN ('media_timing', 'timing_evidence', 'registration_time')),
    ADD COLUMN order_evidence_id uuid,
    ADD COLUMN order_evidence_revision bigint,
    ADD COLUMN order_evidence_qualification text,
    ADD CONSTRAINT assembly_member_order_evidence_fk
        FOREIGN KEY (asset_id, order_evidence_id)
        REFERENCES stageflow.media_timing_evidence(asset_id, evidence_id),
    ADD CONSTRAINT assembly_member_order_evidence_set_check
        CHECK ((order_source IS NOT DISTINCT FROM 'timing_evidence'
                AND order_evidence_id IS NOT NULL AND order_evidence_revision IS NOT NULL
                AND order_evidence_qualification IS NOT NULL)
               OR (order_source IS DISTINCT FROM 'timing_evidence'
                   AND order_evidence_id IS NULL AND order_evidence_revision IS NULL
                   AND order_evidence_qualification IS NULL)),
    ADD CONSTRAINT assembly_member_order_evidence_qualification_check
        CHECK (order_evidence_qualification IN ('unqualified', 'qualified', 'rejected', 'expired'));

INSERT INTO stageflow.schema_migration(version) VALUES ('0018_assembly_timing_evidence');
