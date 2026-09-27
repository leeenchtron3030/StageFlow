-- Reuse asset/manifest and execution-profile identity; no placeholder transcription input.
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT work_operation_operation_kind_check,
    ADD CONSTRAINT work_operation_operation_kind_check
        CHECK (operation_kind IN ('transcription', 'render', 'media_timing')),
    DROP CONSTRAINT work_operation_transcription_source_check,
    ADD CONSTRAINT work_operation_transcription_source_check CHECK (
        (operation_kind <> 'transcription' OR asset_format IS NOT NULL)
        AND (operation_kind NOT IN ('transcription', 'media_timing') OR (
            asset_id IS NOT NULL AND manifest_id IS NOT NULL AND manifest_version IS NOT NULL
        ))
    ),
    ADD COLUMN terminal_result_media_timing_evidence_id uuid,
    ADD CONSTRAINT work_operation_media_timing_evidence_fk
        FOREIGN KEY (asset_id, terminal_result_media_timing_evidence_id)
        REFERENCES stageflow.media_timing_evidence(asset_id, evidence_id),
    ADD CONSTRAINT work_operation_render_result_kind_check CHECK (
        operation_kind = 'render' OR terminal_result_rendered_output_id IS NULL
    ),
    ADD CONSTRAINT work_operation_media_timing_result_kind_check CHECK (
        operation_kind = 'media_timing' OR terminal_result_media_timing_evidence_id IS NULL
    ),
    DROP CONSTRAINT work_operation_check4,
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
-- The existing transcription-result constraint already excludes both other kinds.
ALTER TABLE stageflow.work_worker_capability
    DROP CONSTRAINT work_worker_capability_operation_kind_check,
    ADD CONSTRAINT work_worker_capability_operation_kind_check
        CHECK (operation_kind IN ('transcription', 'render', 'media_timing')),
    ADD CONSTRAINT work_worker_capability_media_timing_fields_check CHECK (
        operation_kind <> 'media_timing' OR (
            accepted_asset_formats IS NULL AND NOT supports_word_timing
            AND NOT supports_speaker_labels AND provider_id IS NULL
            AND provider_version IS NULL AND model_id IS NULL AND model_version IS NULL
        )
    );

INSERT INTO stageflow.schema_migration (version) VALUES ('0017_media_timing_operation');
