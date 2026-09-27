-- Serialize the guard with operation/capability writes; never discard timing work or references.
LOCK TABLE stageflow.work_operation, stageflow.work_worker_capability IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.work_operation
               WHERE terminal_result_media_timing_evidence_id IS NOT NULL) THEN
        RAISE EXCEPTION 'cannot reverse 0017: media_timing result references exist';
    END IF;
    IF EXISTS (SELECT 1 FROM stageflow.work_operation WHERE operation_kind = 'media_timing') THEN
        RAISE EXCEPTION 'cannot reverse 0017: media_timing operations exist';
    END IF;
    IF EXISTS (SELECT 1 FROM stageflow.work_worker_capability
               WHERE operation_kind = 'media_timing') THEN
        RAISE EXCEPTION 'cannot reverse 0017: media_timing capabilities exist';
    END IF;
END;
$$;
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT work_operation_media_timing_evidence_fk,
    DROP CONSTRAINT work_operation_render_result_kind_check,
    DROP CONSTRAINT work_operation_media_timing_result_kind_check,
    DROP CONSTRAINT work_operation_check4,
    DROP COLUMN terminal_result_media_timing_evidence_id,
    DROP CONSTRAINT work_operation_operation_kind_check,
    ADD CONSTRAINT work_operation_operation_kind_check
        CHECK (operation_kind IN ('transcription', 'render')),
    DROP CONSTRAINT work_operation_transcription_source_check,
    ADD CONSTRAINT work_operation_transcription_source_check CHECK (
        operation_kind <> 'transcription' OR (
            asset_id IS NOT NULL AND manifest_id IS NOT NULL
            AND manifest_version IS NOT NULL AND asset_format IS NOT NULL
        )
    ),
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
        )
    );
ALTER TABLE stageflow.work_worker_capability
    DROP CONSTRAINT work_worker_capability_media_timing_fields_check,
    DROP CONSTRAINT work_worker_capability_operation_kind_check,
    ADD CONSTRAINT work_worker_capability_operation_kind_check
        CHECK (operation_kind IN ('transcription', 'render'));
DELETE FROM stageflow.schema_migration WHERE version = '0017_media_timing_operation';
