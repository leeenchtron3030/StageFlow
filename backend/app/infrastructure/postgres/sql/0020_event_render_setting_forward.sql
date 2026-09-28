CREATE TABLE stageflow.event_render_setting (
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    version bigint NOT NULL CHECK (version > 0),
    render_profile_id text NOT NULL CHECK (btrim(render_profile_id) <> ''),
    render_profile_version text NOT NULL CHECK (btrim(render_profile_version) <> ''),
    video_bit_rate bigint CHECK (video_bit_rate > 0),
    audio_bit_rate bigint CHECK (audio_bit_rate > 0),
    command_id uuid NOT NULL UNIQUE,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    selected_by uuid NOT NULL,
    selected_at timestamptz NOT NULL,
    PRIMARY KEY (event_id, version)
);
CREATE TRIGGER event_render_setting_immutable
    BEFORE UPDATE OR DELETE ON stageflow.event_render_setting
    FOR EACH ROW EXECUTE FUNCTION stageflow.render_history_is_immutable();

-- No existing rows are updated; existing constraints and triggers are untouched.
ALTER TABLE stageflow.render_operation_input
    ADD COLUMN video_bit_rate bigint CHECK (video_bit_rate > 0),
    ADD COLUMN audio_bit_rate bigint CHECK (audio_bit_rate > 0),
    ADD COLUMN event_render_setting_version bigint CHECK (event_render_setting_version > 0);

INSERT INTO stageflow.schema_migration (version) VALUES ('0020_event_render_setting');
