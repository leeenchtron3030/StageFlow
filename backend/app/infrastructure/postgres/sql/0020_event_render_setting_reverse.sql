DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.event_render_setting)
       OR EXISTS (SELECT 1 FROM stageflow.render_operation_input
                  WHERE video_bit_rate IS NOT NULL OR audio_bit_rate IS NOT NULL
                     OR event_render_setting_version IS NOT NULL) THEN
        RAISE EXCEPTION 'event_render_setting_reverse_refused: recorded render settings exist';
    END IF;
END;
$$;

ALTER TABLE stageflow.render_operation_input
    DROP COLUMN event_render_setting_version,
    DROP COLUMN audio_bit_rate,
    DROP COLUMN video_bit_rate;
DROP TABLE stageflow.event_render_setting;
DELETE FROM stageflow.schema_migration WHERE version = '0020_event_render_setting';
