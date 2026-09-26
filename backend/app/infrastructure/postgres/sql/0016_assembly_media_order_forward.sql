-- Preserve existing positions and immutable history: no backfill or row updates.
ALTER TABLE stageflow.assembly_member
    ADD COLUMN order_source text,
    ADD COLUMN order_key_at timestamptz,
    ADD CONSTRAINT assembly_member_order_source_check
        CHECK (order_source IN ('media_timing', 'registration_time')),
    ADD CONSTRAINT assembly_member_order_pair_check
        CHECK ((order_source IS NULL) = (order_key_at IS NULL)),
    ADD CONSTRAINT assembly_member_media_order_key_check
        CHECK (order_source IS DISTINCT FROM 'media_timing'
               OR (media_started_at IS NOT NULL AND order_key_at = media_started_at));

INSERT INTO stageflow.schema_migration(version) VALUES ('0016_assembly_media_order');
