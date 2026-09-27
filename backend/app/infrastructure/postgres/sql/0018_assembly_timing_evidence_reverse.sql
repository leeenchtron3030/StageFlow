-- Refuse loss of frozen advisory provenance; serialize against concurrent proposals.
LOCK TABLE stageflow.assembly_member IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.assembly_member
               WHERE order_source = 'timing_evidence') THEN
        RAISE EXCEPTION 'assembly_timing_evidence_reverse_requires_no_timing_evidence_members';
    END IF;
END;
$$;

ALTER TABLE stageflow.assembly_member
    DROP CONSTRAINT assembly_member_order_evidence_fk,
    DROP CONSTRAINT assembly_member_order_evidence_set_check,
    DROP CONSTRAINT assembly_member_order_evidence_qualification_check,
    DROP COLUMN order_evidence_id,
    DROP COLUMN order_evidence_revision,
    DROP COLUMN order_evidence_qualification,
    DROP CONSTRAINT assembly_member_order_source_check,
    ADD CONSTRAINT assembly_member_order_source_check
        CHECK (order_source IN ('media_timing', 'registration_time'));

DELETE FROM stageflow.schema_migration WHERE version = '0018_assembly_timing_evidence';
