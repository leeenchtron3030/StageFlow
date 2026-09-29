-- A prior manual list must never silently become a composition-owned list.
LOCK TABLE stageflow.editorial_phrase_list IN SHARE ROW EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.editorial_phrase_list
               WHERE phrase_key IN ('boundary-cues-start', 'boundary-cues-end')) THEN
        RAISE EXCEPTION 'boundary_cue_reserved_key_exists';
    END IF;
END;
$$;

CREATE TABLE stageflow.boundary_cue_composition (
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    version integer NOT NULL CHECK (version > 0),
    command_id uuid NOT NULL UNIQUE,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    catalog_id text NOT NULL CHECK (catalog_id = 'boundary-cue-catalog'),
    catalog_version integer NOT NULL CHECK (catalog_version > 0),
    catalog_digest text NOT NULL CHECK (catalog_digest ~ '^[0-9a-f]{64}$'),
    profile_key text CHECK (length(profile_key) BETWEEN 1 AND 100),
    composed_by uuid NOT NULL,
    composed_at timestamptz NOT NULL,
    start_phrase_list_id uuid NOT NULL,
    start_phrase_list_version bigint NOT NULL,
    end_phrase_list_id uuid NOT NULL,
    end_phrase_list_version bigint NOT NULL,
    group_count integer NOT NULL CHECK (group_count BETWEEN 0 AND 20),
    choice_count integer NOT NULL CHECK (choice_count BETWEEN 0 AND 800),
    custom_count integer NOT NULL CHECK (custom_count BETWEEN 0 AND 400),
    segment_count integer NOT NULL CHECK (segment_count BETWEEN 0 AND 400),
    PRIMARY KEY (event_id, version),
    FOREIGN KEY (start_phrase_list_id, start_phrase_list_version)
        REFERENCES stageflow.editorial_phrase_list(phrase_list_id, version),
    FOREIGN KEY (end_phrase_list_id, end_phrase_list_version)
        REFERENCES stageflow.editorial_phrase_list(phrase_list_id, version),
    CHECK (start_phrase_list_version = version AND end_phrase_list_version = version)
);

CREATE TABLE stageflow.boundary_cue_group (
    event_id uuid NOT NULL,
    version integer NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 19),
    group_key text NOT NULL CHECK (length(group_key) BETWEEN 1 AND 100),
    group_version integer NOT NULL CHECK (group_version > 0),
    PRIMARY KEY (event_id, version, ordinal),
    UNIQUE (event_id, version, group_key),
    FOREIGN KEY (event_id, version) REFERENCES stageflow.boundary_cue_composition(event_id, version)
);
CREATE TABLE stageflow.boundary_cue_choice (
    event_id uuid NOT NULL,
    version integer NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 799),
    kind text NOT NULL CHECK (kind IN ('include', 'exclude')),
    group_key text NOT NULL,
    phrase text NOT NULL CHECK (length(btrim(phrase)) BETWEEN 1 AND 100),
    PRIMARY KEY (event_id, version, ordinal),
    UNIQUE (event_id, version, group_key, phrase),
    FOREIGN KEY (event_id, version, group_key)
        REFERENCES stageflow.boundary_cue_group(event_id, version, group_key)
);
CREATE TABLE stageflow.boundary_cue_custom_phrase (
    event_id uuid NOT NULL,
    version integer NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 399),
    phrase text NOT NULL CHECK (length(btrim(phrase)) BETWEEN 1 AND 100),
    role text NOT NULL CHECK (role IN ('start', 'end', 'changeover')),
    PRIMARY KEY (event_id, version, ordinal),
    FOREIGN KEY (event_id, version) REFERENCES stageflow.boundary_cue_composition(event_id, version)
);
CREATE TABLE stageflow.boundary_cue_segment_phrase (
    event_id uuid NOT NULL,
    version integer NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal BETWEEN 0 AND 399),
    phrase text NOT NULL CHECK (length(btrim(phrase)) BETWEEN 1 AND 100),
    source_group text NOT NULL,
    PRIMARY KEY (event_id, version, ordinal),
    UNIQUE (event_id, version, source_group, phrase),
    FOREIGN KEY (event_id, version, source_group)
        REFERENCES stageflow.boundary_cue_group(event_id, version, group_key)
);

CREATE FUNCTION stageflow.boundary_cue_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'boundary_cue_composition_immutable';
END;
$$;
CREATE TRIGGER boundary_cue_composition_immutable
    BEFORE UPDATE OR DELETE ON stageflow.boundary_cue_composition
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_immutable();
CREATE TRIGGER boundary_cue_group_immutable
    BEFORE UPDATE OR DELETE ON stageflow.boundary_cue_group
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_immutable();
CREATE TRIGGER boundary_cue_choice_immutable
    BEFORE UPDATE OR DELETE ON stageflow.boundary_cue_choice
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_immutable();
CREATE TRIGGER boundary_cue_custom_phrase_immutable
    BEFORE UPDATE OR DELETE ON stageflow.boundary_cue_custom_phrase
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_immutable();
CREATE TRIGGER boundary_cue_segment_phrase_immutable
    BEFORE UPDATE OR DELETE ON stageflow.boundary_cue_segment_phrase
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_immutable();

-- Header counts fix child membership. A deferred check permits atomic insertion
-- while refusing both incomplete publication and later extension of history.
CREATE FUNCTION stageflow.boundary_cue_complete() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE header stageflow.boundary_cue_composition; item record;
BEGIN
    SELECT * INTO STRICT header FROM stageflow.boundary_cue_composition
        WHERE event_id=NEW.event_id AND version=NEW.version;
    FOR item IN
        SELECT count(*) AS actual, max(ordinal) AS last, header.group_count AS expected
            FROM stageflow.boundary_cue_group WHERE event_id=NEW.event_id AND version=NEW.version
        UNION ALL
        SELECT count(*), max(ordinal), header.choice_count FROM stageflow.boundary_cue_choice
            WHERE event_id=NEW.event_id AND version=NEW.version
        UNION ALL
        SELECT count(*), max(ordinal), header.custom_count FROM stageflow.boundary_cue_custom_phrase
            WHERE event_id=NEW.event_id AND version=NEW.version
        UNION ALL
        SELECT count(*), max(ordinal), header.segment_count FROM stageflow.boundary_cue_segment_phrase
            WHERE event_id=NEW.event_id AND version=NEW.version
    LOOP
        IF item.actual <> item.expected OR (item.actual > 0 AND item.last <> item.actual - 1) THEN
            RAISE EXCEPTION 'boundary_cue_membership_incomplete';
        END IF;
    END LOOP;
    IF NOT EXISTS (SELECT 1 FROM stageflow.editorial_phrase_list
        WHERE phrase_list_id=header.start_phrase_list_id AND version=header.start_phrase_list_version
            AND event_id=header.event_id AND phrase_key='boundary-cues-start')
       OR NOT EXISTS (SELECT 1 FROM stageflow.editorial_phrase_list
        WHERE phrase_list_id=header.end_phrase_list_id AND version=header.end_phrase_list_version
            AND event_id=header.event_id AND phrase_key='boundary-cues-end') THEN
        RAISE EXCEPTION 'boundary_cue_list_scope_mismatch';
    END IF;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER boundary_cue_header_complete
    AFTER INSERT ON stageflow.boundary_cue_composition DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_complete();
CREATE CONSTRAINT TRIGGER boundary_cue_groups_complete
    AFTER INSERT ON stageflow.boundary_cue_group DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_complete();
CREATE CONSTRAINT TRIGGER boundary_cue_choices_complete
    AFTER INSERT ON stageflow.boundary_cue_choice DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_complete();
CREATE CONSTRAINT TRIGGER boundary_cue_custom_complete
    AFTER INSERT ON stageflow.boundary_cue_custom_phrase DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_complete();
CREATE CONSTRAINT TRIGGER boundary_cue_segments_complete
    AFTER INSERT ON stageflow.boundary_cue_segment_phrase DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION stageflow.boundary_cue_complete();

INSERT INTO stageflow.schema_migration(version) VALUES ('0025_boundary_cue_composition');
