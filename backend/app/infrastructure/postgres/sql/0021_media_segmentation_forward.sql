-- Add only segmentation storage and kind-specific constraints; existing kinds stay exact.
CREATE TABLE stageflow.media_segmentation_evidence (
    evidence_id uuid PRIMARY KEY,
    operation_id uuid NOT NULL UNIQUE REFERENCES stageflow.work_operation(operation_id),
    asset_id uuid NOT NULL REFERENCES stageflow.completed_media_asset_registry(asset_id),
    manifest_id uuid NOT NULL,
    manifest_version text NOT NULL CHECK (manifest_version ~ '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$'),
    producing_attempt_id uuid NOT NULL REFERENCES stageflow.work_operation_attempt(attempt_id),
    profile_id text NOT NULL CHECK (profile_id = 'freeze-silence'),
    profile_version text NOT NULL CHECK (profile_version = '1'),
    video_filter text NOT NULL CHECK (video_filter = 'fps=5,scale=320:-2,freezedetect=n=0.003:d=4'),
    audio_filter text NOT NULL CHECK (audio_filter = 'silencedetect=n=-40dB:d=3'),
    decode text NOT NULL CHECK (decode = 'cpu'),
    demuxer_allowlist text NOT NULL CHECK (
        demuxer_allowlist = 'mov,mp4,m4a,3gp,3g2,mj2,matroska,webm,mxf,wav'),
    duration_microseconds bigint NOT NULL CHECK (
        duration_microseconds > 0 AND duration_microseconds <= 315576000000000),
    interval_count integer NOT NULL CHECK (interval_count BETWEEN 0 AND 10000),
    ffmpeg_version text NOT NULL CHECK (ffmpeg_version ~ '^[A-Za-z0-9][A-Za-z0-9._+~-]{0,127}$'),
    ffmpeg_sha256 text NOT NULL CHECK (ffmpeg_sha256 ~ '^[0-9a-f]{64}$'),
    inspected_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    UNIQUE (operation_id, evidence_id),
    UNIQUE (evidence_id, profile_id, profile_version)
);
CREATE INDEX media_segmentation_evidence_asset_idx
    ON stageflow.media_segmentation_evidence(asset_id, evidence_id);
CREATE TABLE stageflow.media_segmentation_interval (
    evidence_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 9999),
    kind text NOT NULL CHECK (kind IN ('freeze', 'silence')),
    start_microseconds bigint NOT NULL CHECK (start_microseconds >= 0),
    end_microseconds bigint NOT NULL CHECK (
        end_microseconds > start_microseconds AND end_microseconds <= 315576000000000),
    profile_id text NOT NULL,
    profile_version text NOT NULL,
    PRIMARY KEY (evidence_id, ordinal),
    FOREIGN KEY (evidence_id, profile_id, profile_version)
        REFERENCES stageflow.media_segmentation_evidence(evidence_id, profile_id, profile_version)
);
CREATE FUNCTION stageflow.segmentation_matches_operation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM stageflow.work_operation o
        JOIN stageflow.work_operation_attempt a USING (operation_id)
        WHERE o.operation_id = NEW.operation_id AND o.operation_kind = 'media_segmentation'
          AND o.asset_id = NEW.asset_id AND o.manifest_id = NEW.manifest_id
          AND o.manifest_version = NEW.manifest_version
          AND o.execution_profile_id = NEW.profile_id
          AND o.execution_profile_version = NEW.profile_version
          AND a.attempt_id = NEW.producing_attempt_id
    ) THEN
        RAISE EXCEPTION 'media_segmentation_identity_conflict';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER segmentation_matches_operation BEFORE INSERT ON stageflow.media_segmentation_evidence
    FOR EACH ROW EXECUTE FUNCTION stageflow.segmentation_matches_operation();
CREATE FUNCTION stageflow.segmentation_intervals_complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    expected integer;
    duration bigint;
BEGIN
    SELECT interval_count, duration_microseconds INTO expected, duration
        FROM stageflow.media_segmentation_evidence WHERE evidence_id = NEW.evidence_id;
    IF (SELECT count(*) FROM stageflow.media_segmentation_interval
        WHERE evidence_id = NEW.evidence_id) <> expected OR EXISTS (
        SELECT 1 FROM (
            SELECT *, lag(end_microseconds) OVER (PARTITION BY kind ORDER BY ordinal) AS previous_end
            FROM stageflow.media_segmentation_interval WHERE evidence_id = NEW.evidence_id
        ) i WHERE ordinal >= expected OR end_microseconds > duration
            OR start_microseconds < previous_end
    ) THEN
        RAISE EXCEPTION 'media_segmentation_intervals_invalid';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER segmentation_evidence_complete
    AFTER INSERT ON stageflow.media_segmentation_evidence DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.segmentation_intervals_complete();
-- The parent's deferred check runs once, not once per interval. Ordinals are unique
-- and bounded by its immutable count, so a complete committed result cannot be appended to.
CREATE FUNCTION stageflow.segmentation_interval_bounds() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM stageflow.media_segmentation_evidence
        WHERE evidence_id = NEW.evidence_id AND NEW.ordinal < interval_count
          AND NEW.end_microseconds <= duration_microseconds
    ) THEN
        RAISE EXCEPTION 'media_segmentation_interval_bounds';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER segmentation_interval_bounds BEFORE INSERT ON stageflow.media_segmentation_interval
    FOR EACH ROW EXECUTE FUNCTION stageflow.segmentation_interval_bounds();
CREATE FUNCTION stageflow.segmentation_history_is_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'media_segmentation_history_is_immutable';
END;
$$;
CREATE TRIGGER segmentation_evidence_immutable
    BEFORE UPDATE OR DELETE ON stageflow.media_segmentation_evidence
    FOR EACH ROW EXECUTE FUNCTION stageflow.segmentation_history_is_immutable();
CREATE TRIGGER segmentation_interval_immutable
    BEFORE UPDATE OR DELETE ON stageflow.media_segmentation_interval
    FOR EACH ROW EXECUTE FUNCTION stageflow.segmentation_history_is_immutable();
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT work_operation_operation_kind_check,
    ADD CONSTRAINT work_operation_operation_kind_check CHECK (
        operation_kind IN ('transcription', 'render', 'media_timing', 'media_segmentation')),
    ADD CONSTRAINT work_operation_segmentation_source_check CHECK (
        operation_kind <> 'media_segmentation' OR (
            asset_id IS NOT NULL AND manifest_id IS NOT NULL AND manifest_version IS NOT NULL
            AND asset_format IS NULL AND requested_language IS NULL
            AND NOT request_word_timing AND NOT request_speaker_labels AND NOT requires_cloud)),
    ADD COLUMN terminal_result_media_segmentation_evidence_id uuid,
    ADD CONSTRAINT work_operation_segmentation_evidence_fk
        FOREIGN KEY (operation_id, terminal_result_media_segmentation_evidence_id)
        REFERENCES stageflow.media_segmentation_evidence(operation_id, evidence_id),
    ADD CONSTRAINT work_operation_segmentation_result_kind_check CHECK (
        operation_kind = 'media_segmentation' OR terminal_result_media_segmentation_evidence_id IS NULL),
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
            OR (operation_kind = 'media_segmentation'
                AND terminal_result_type = 'media_segmentation_evidence'
                AND terminal_result_type IS NOT NULL
                AND terminal_result_media_segmentation_evidence_id IS NOT NULL)
        )
    );
ALTER TABLE stageflow.work_worker_capability
    DROP CONSTRAINT work_worker_capability_operation_kind_check,
    ADD CONSTRAINT work_worker_capability_operation_kind_check CHECK (
        operation_kind IN ('transcription', 'render', 'media_timing', 'media_segmentation')),
    ADD CONSTRAINT work_worker_capability_segmentation_fields_check CHECK (
        operation_kind <> 'media_segmentation' OR (
            accepted_asset_formats IS NULL AND NOT supports_word_timing
            AND NOT supports_speaker_labels AND provider_id IS NULL
            AND provider_version IS NULL AND model_id IS NULL AND model_version IS NULL
            AND locality = 'local'));
INSERT INTO stageflow.schema_migration (version) VALUES ('0021_media_segmentation');
