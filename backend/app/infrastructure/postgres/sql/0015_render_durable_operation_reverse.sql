-- Refuse reversal rather than remove render identities or restore invalid constraints.
-- Lock before checking so concurrent render inserts cannot race the guard.
LOCK TABLE stageflow.work_operation, stageflow.work_worker_capability,
    stageflow.render_operation_input, stageflow.rendered_output IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.work_operation WHERE operation_kind = 'render')
       OR EXISTS (SELECT 1 FROM stageflow.rendered_output)
       OR EXISTS (SELECT 1 FROM stageflow.render_operation_input)
       OR EXISTS (SELECT 1 FROM stageflow.work_worker_capability WHERE operation_kind = 'render')
    THEN
        RAISE EXCEPTION 'cannot reverse 0015: render operations, inputs, outputs or capabilities exist';
    END IF;
END;
$$;
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT IF EXISTS work_operation_transcription_result_check,
    DROP CONSTRAINT IF EXISTS work_operation_rendered_output_fk,
    DROP CONSTRAINT work_operation_check4,
    DROP COLUMN terminal_result_rendered_output_id,
    ADD CONSTRAINT work_operation_check4 CHECK (
        operation_status <> 'succeeded' OR (
            terminal_result_type IS NOT NULL AND terminal_result_id IS NOT NULL
            AND terminal_result_revision IS NOT NULL
        )
    ),
    DROP CONSTRAINT IF EXISTS work_operation_transcription_source_check,
    ALTER COLUMN asset_id SET NOT NULL,
    ALTER COLUMN manifest_id SET NOT NULL,
    ALTER COLUMN manifest_version SET NOT NULL,
    ALTER COLUMN asset_format SET NOT NULL,
    DROP CONSTRAINT work_operation_operation_kind_check,
    ADD CONSTRAINT work_operation_operation_kind_check CHECK (operation_kind = 'transcription');
ALTER TABLE stageflow.work_worker_capability
    ALTER COLUMN accepted_asset_formats SET NOT NULL,
    DROP CONSTRAINT work_worker_capability_accepted_asset_formats_check,
    ADD CONSTRAINT work_worker_capability_accepted_asset_formats_check
        CHECK (cardinality(accepted_asset_formats) > 0),
    DROP CONSTRAINT work_worker_capability_operation_kind_check,
    ADD CONSTRAINT work_worker_capability_operation_kind_check CHECK (operation_kind = 'transcription');
DROP TABLE stageflow.rendered_output;
DROP TABLE stageflow.render_operation_input;
DROP FUNCTION stageflow.render_output_matches_attempt();
DROP FUNCTION stageflow.render_input_matches_operation();
DROP FUNCTION stageflow.render_history_is_immutable();
DELETE FROM stageflow.schema_migration WHERE version = '0015_render_durable_operation';
