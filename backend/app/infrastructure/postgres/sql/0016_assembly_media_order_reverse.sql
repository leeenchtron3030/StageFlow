-- Only registration-time ordering would lose its meaning on reversal.
-- Lock before checking so a concurrent fallback insert cannot race the guard.
LOCK TABLE stageflow.assembly_member IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.assembly_member
               WHERE order_source = 'registration_time') THEN
        RAISE EXCEPTION 'assembly_media_order_reverse_requires_no_registration_time_members';
    END IF;
END;
$$;

ALTER TABLE stageflow.assembly_member
    DROP CONSTRAINT assembly_member_media_order_key_check,
    DROP CONSTRAINT assembly_member_order_pair_check,
    DROP CONSTRAINT assembly_member_order_source_check,
    DROP COLUMN order_key_at,
    DROP COLUMN order_source;

DELETE FROM stageflow.schema_migration WHERE version = '0016_assembly_media_order';
