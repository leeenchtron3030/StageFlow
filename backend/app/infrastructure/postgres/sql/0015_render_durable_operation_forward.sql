-- Add render persistence without changing transcription identities or foreign keys.
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT work_operation_operation_kind_check,
    ADD CONSTRAINT work_operation_operation_kind_check
        CHECK (operation_kind IN ('transcription', 'render')),
    ALTER COLUMN asset_id DROP NOT NULL,
    ALTER COLUMN manifest_id DROP NOT NULL,
    ALTER COLUMN manifest_version DROP NOT NULL,
    ALTER COLUMN asset_format DROP NOT NULL,
    ADD CONSTRAINT work_operation_transcription_source_check CHECK (
        operation_kind <> 'transcription' OR (
            asset_id IS NOT NULL AND manifest_id IS NOT NULL
            AND manifest_version IS NOT NULL AND asset_format IS NOT NULL
        )
    );
ALTER TABLE stageflow.work_worker_capability
    DROP CONSTRAINT work_worker_capability_operation_kind_check,
    ADD CONSTRAINT work_worker_capability_operation_kind_check
        CHECK (operation_kind IN ('transcription', 'render')),
    ALTER COLUMN accepted_asset_formats DROP NOT NULL,
    DROP CONSTRAINT work_worker_capability_accepted_asset_formats_check,
    ADD CONSTRAINT work_worker_capability_accepted_asset_formats_check CHECK (
        operation_kind <> 'transcription' OR (
            accepted_asset_formats IS NOT NULL AND cardinality(accepted_asset_formats) > 0
        )
    );

CREATE TABLE stageflow.render_operation_input (
    operation_id uuid PRIMARY KEY REFERENCES stageflow.work_operation(operation_id),
    assembly_revision_id uuid NOT NULL REFERENCES stageflow.assembly_revision(revision_id),
    render_profile_id text NOT NULL CHECK (btrim(render_profile_id) <> ''),
    render_profile_version text NOT NULL CHECK (btrim(render_profile_version) <> ''),
    output_token text NOT NULL CHECK (output_token ~ '^[A-Za-z0-9_-]{1,128}$'),
    UNIQUE (operation_id, assembly_revision_id, render_profile_id, render_profile_version)
);
CREATE FUNCTION stageflow.render_input_matches_operation() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM stageflow.work_operation
        WHERE operation_id = NEW.operation_id AND operation_kind = 'render'
          AND execution_profile_id = NEW.render_profile_id
          AND execution_profile_version = NEW.render_profile_version
    ) THEN
        RAISE EXCEPTION 'render_input_operation_mismatch';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER render_input_matches_operation BEFORE INSERT ON stageflow.render_operation_input
    FOR EACH ROW EXECUTE FUNCTION stageflow.render_input_matches_operation();

CREATE TABLE stageflow.rendered_output (
    output_id uuid PRIMARY KEY,
    assembly_revision_id uuid NOT NULL REFERENCES stageflow.assembly_revision(revision_id),
    render_profile_id text NOT NULL CHECK (btrim(render_profile_id) <> ''),
    render_profile_version text NOT NULL CHECK (btrim(render_profile_version) <> ''),
    operation_id uuid NOT NULL REFERENCES stageflow.work_operation(operation_id),
    producing_attempt_id uuid NOT NULL REFERENCES stageflow.work_operation_attempt(attempt_id),
    content_key text NOT NULL CHECK (content_key ~ '^[A-Za-z0-9_-]{1,128}$'),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    manifest_content_key text NOT NULL CHECK (manifest_content_key ~ '^[A-Za-z0-9_-]{1,128}$'),
    manifest_sha256 text NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    byte_size bigint NOT NULL CHECK (byte_size > 0),
    media_type text NOT NULL CHECK (btrim(media_type) <> ''),
    duration_microseconds bigint NOT NULL CHECK (duration_microseconds > 0),
    frame_count bigint NOT NULL CHECK (frame_count > 0),
    ffmpeg_version text NOT NULL CHECK (btrim(ffmpeg_version) <> ''),
    ffmpeg_sha256 text NOT NULL CHECK (ffmpeg_sha256 ~ '^[0-9a-f]{64}$'),
    produced_at timestamptz NOT NULL,
    UNIQUE (operation_id),
    UNIQUE (operation_id, output_id),
    FOREIGN KEY (operation_id, assembly_revision_id, render_profile_id, render_profile_version)
        REFERENCES stageflow.render_operation_input (
            operation_id, assembly_revision_id, render_profile_id, render_profile_version
        )
);
CREATE FUNCTION stageflow.render_output_matches_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM stageflow.work_operation_attempt
        WHERE attempt_id = NEW.producing_attempt_id AND operation_id = NEW.operation_id
    ) THEN
        RAISE EXCEPTION 'render_output_attempt_mismatch';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER render_output_matches_attempt BEFORE INSERT ON stageflow.rendered_output
    FOR EACH ROW EXECUTE FUNCTION stageflow.render_output_matches_attempt();
CREATE FUNCTION stageflow.render_history_is_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'render_history_is_immutable';
END;
$$;
CREATE TRIGGER rendered_output_immutable BEFORE UPDATE OR DELETE ON stageflow.rendered_output
    FOR EACH ROW EXECUTE FUNCTION stageflow.render_history_is_immutable();
CREATE TRIGGER render_operation_input_immutable
    BEFORE UPDATE OR DELETE ON stageflow.render_operation_input
    FOR EACH ROW EXECUTE FUNCTION stageflow.render_history_is_immutable();

ALTER TABLE stageflow.work_operation
    ADD COLUMN terminal_result_rendered_output_id uuid,
    ADD CONSTRAINT work_operation_transcription_result_check CHECK (
        operation_kind = 'transcription'
        OR (terminal_result_id IS NULL AND terminal_result_revision IS NULL)
    ),
    ADD CONSTRAINT work_operation_rendered_output_fk
        FOREIGN KEY (operation_id, terminal_result_rendered_output_id)
        REFERENCES stageflow.rendered_output(operation_id, output_id)
        DEFERRABLE INITIALLY DEFERRED,
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
        )
    );

INSERT INTO stageflow.schema_migration (version) VALUES ('0015_render_durable_operation');
