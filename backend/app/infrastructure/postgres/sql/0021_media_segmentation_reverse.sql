LOCK TABLE stageflow.work_operation, stageflow.work_worker_capability,
    stageflow.media_segmentation_evidence, stageflow.media_segmentation_interval
    IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.work_operation WHERE operation_kind = 'media_segmentation'
               OR terminal_result_media_segmentation_evidence_id IS NOT NULL)
       OR EXISTS (SELECT 1 FROM stageflow.work_worker_capability
                  WHERE operation_kind = 'media_segmentation')
       OR EXISTS (SELECT 1 FROM stageflow.media_segmentation_evidence)
       OR EXISTS (SELECT 1 FROM stageflow.media_segmentation_interval) THEN
        RAISE EXCEPTION 'cannot reverse 0021: media_segmentation rows exist';
    END IF;
END;
$$;
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT work_operation_segmentation_evidence_fk,
    DROP CONSTRAINT work_operation_segmentation_result_kind_check,
    DROP CONSTRAINT work_operation_segmentation_source_check,
    DROP CONSTRAINT work_operation_check4,
    DROP COLUMN terminal_result_media_segmentation_evidence_id,
    DROP CONSTRAINT work_operation_operation_kind_check,
    ADD CONSTRAINT work_operation_operation_kind_check CHECK (
        operation_kind IN ('transcription', 'render', 'media_timing')),
    ADD CONSTRAINT work_operation_check4 CHECK (
        operation_status <> 'succeeded' OR (
            (operation_kind = 'transcription'
                AND terminal_result_type IS NOT NULL
                AND terminal_result_id IS NOT NULL
                AND terminal_result_revision IS NOT NULL)
            OR (operation_kind = 'render'
                AND terminal_result_type = 'rendered_output'
                AND terminal_result_type IS NOT NULL
                AND terminal_result_rendered_output_id IS NOT NULL)
            OR (operation_kind = 'media_timing'
                AND terminal_result_type = 'media_timing_evidence'
                AND terminal_result_type IS NOT NULL
                AND terminal_result_media_timing_evidence_id IS NOT NULL)
        )
    );

ALTER TABLE stageflow.work_worker_capability
    DROP CONSTRAINT work_worker_capability_segmentation_fields_check,
    DROP CONSTRAINT work_worker_capability_operation_kind_check,
    ADD CONSTRAINT work_worker_capability_operation_kind_check CHECK (
        operation_kind IN ('transcription', 'render', 'media_timing'));
DROP TABLE stageflow.media_segmentation_interval;
DROP TABLE stageflow.media_segmentation_evidence;
DROP FUNCTION stageflow.segmentation_matches_operation();
DROP FUNCTION stageflow.segmentation_intervals_complete();
DROP FUNCTION stageflow.segmentation_interval_bounds();
DROP FUNCTION stageflow.segmentation_history_is_immutable();
DELETE FROM stageflow.schema_migration WHERE version = '0021_media_segmentation';
