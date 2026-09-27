CREATE TABLE stageflow.editorial_phrase_list (
    phrase_list_id uuid NOT NULL,
    event_id uuid NOT NULL REFERENCES stageflow.business_event(event_id),
    phrase_key text NOT NULL CHECK (length(btrim(phrase_key)) BETWEEN 1 AND 100),
    version bigint NOT NULL CHECK (version > 0),
    name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
    phrases text[] NOT NULL CHECK (cardinality(phrases) BETWEEN 1 AND 200),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (phrase_list_id, version),
    UNIQUE (event_id, phrase_key, version)
);

CREATE TABLE stageflow.editorial_derivation_run (
    run_id uuid PRIMARY KEY,
    session_id uuid NOT NULL REFERENCES stageflow.session(session_id),
    phrase_list_id uuid NOT NULL,
    phrase_list_version bigint NOT NULL,
    input_set jsonb NOT NULL CHECK (jsonb_typeof(input_set) = 'array'),
    input_digest text NOT NULL UNIQUE CHECK (input_digest ~ '^[0-9a-f]{64}$'),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL,
    candidate_ids uuid[] NOT NULL CHECK (cardinality(candidate_ids) <= 500),
    no_transcript bigint NOT NULL CHECK (no_transcript >= 0),
    no_timing_evidence bigint NOT NULL CHECK (no_timing_evidence >= 0),
    no_session_start bigint NOT NULL CHECK (no_session_start >= 0),
    outside_session bigint NOT NULL CHECK (outside_session >= 0),
    limit_reached bigint NOT NULL CHECK (limit_reached >= 0),
    FOREIGN KEY (phrase_list_id, phrase_list_version)
        REFERENCES stageflow.editorial_phrase_list(phrase_list_id, version),
    UNIQUE (run_id, phrase_list_id, phrase_list_version)
);

-- Separate immutable receipts allow a new command ID to replay the same input run.
CREATE TABLE stageflow.editorial_derivation_command (
    command_id uuid PRIMARY KEY,
    request_digest text NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
    phrase_list_id uuid,
    phrase_list_version bigint,
    run_id uuid REFERENCES stageflow.editorial_derivation_run(run_id),
    FOREIGN KEY (phrase_list_id, phrase_list_version)
        REFERENCES stageflow.editorial_phrase_list(phrase_list_id, version),
    CHECK (
        (run_id IS NOT NULL AND phrase_list_id IS NULL AND phrase_list_version IS NULL)
        OR (run_id IS NULL AND phrase_list_id IS NOT NULL AND phrase_list_version IS NOT NULL)
    )
);

ALTER TABLE stageflow.editorial_candidate_moment
    DROP CONSTRAINT editorial_candidate_moment_origin_check,
    DROP CONSTRAINT editorial_candidate_moment_epistemic_kind_check,
    DROP CONSTRAINT editorial_candidate_moment_reason_code_check,
    ALTER COLUMN operation_id DROP NOT NULL,
    ADD COLUMN source_kind text NOT NULL DEFAULT 'producer_declaration',
    ADD CONSTRAINT editorial_candidate_moment_kind_check CHECK (
        (origin = 'declared' AND epistemic_kind = 'declared'
         AND reason_code = 'human_mark_moment' AND operation_id IS NOT NULL
         AND source_kind = 'producer_declaration')
        OR
        (origin = 'derived' AND epistemic_kind = 'derived'
         AND reason_code = 'transcript_phrase_match' AND operation_id IS NULL
         AND source_kind = 'transcript_phrase_match' AND timeline_end_microseconds IS NOT NULL)
    );

CREATE TABLE stageflow.editorial_candidate_provenance (
    candidate_moment_id uuid PRIMARY KEY
        REFERENCES stageflow.editorial_candidate_moment(candidate_moment_id),
    run_id uuid NOT NULL,
    phrase_list_id uuid NOT NULL,
    phrase_list_version bigint NOT NULL,
    normalized_phrase text NOT NULL CHECK (btrim(normalized_phrase) <> ''),
    asset_id uuid NOT NULL,
    transcript_evidence_id uuid NOT NULL,
    transcript_revision bigint NOT NULL CHECK (transcript_revision > 0),
    segment_id uuid NOT NULL,
    first_word_id uuid NOT NULL,
    last_word_id uuid NOT NULL,
    asset_start_microseconds bigint NOT NULL CHECK (asset_start_microseconds >= 0),
    asset_end_microseconds bigint NOT NULL CHECK (asset_end_microseconds >= asset_start_microseconds),
    timing_evidence_id uuid NOT NULL,
    timing_revision bigint NOT NULL CHECK (timing_revision > 0),
    timing_qualification text NOT NULL CHECK (
        timing_qualification IN ('unqualified', 'qualified', 'rejected', 'expired')
    ),
    FOREIGN KEY (run_id, phrase_list_id, phrase_list_version)
        REFERENCES stageflow.editorial_derivation_run(run_id, phrase_list_id, phrase_list_version),
    FOREIGN KEY (asset_id, transcript_evidence_id)
        REFERENCES stageflow.transcript_evidence_revision(asset_id, evidence_id),
    FOREIGN KEY (asset_id, timing_evidence_id)
        REFERENCES stageflow.media_timing_evidence(asset_id, evidence_id),
    FOREIGN KEY (transcript_evidence_id, segment_id, first_word_id)
        REFERENCES stageflow.transcript_evidence_word(evidence_id, segment_id, word_id),
    FOREIGN KEY (transcript_evidence_id, segment_id, last_word_id)
        REFERENCES stageflow.transcript_evidence_word(evidence_id, segment_id, word_id)
);

CREATE FUNCTION stageflow.reject_editorial_derivation_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'editorial derivation records are immutable' USING ERRCODE = '23514';
END;
$$;

CREATE TRIGGER editorial_phrase_list_immutable BEFORE UPDATE OR DELETE
    ON stageflow.editorial_phrase_list FOR EACH ROW
    EXECUTE FUNCTION stageflow.reject_editorial_derivation_mutation();
CREATE TRIGGER editorial_derivation_run_immutable BEFORE UPDATE OR DELETE
    ON stageflow.editorial_derivation_run FOR EACH ROW
    EXECUTE FUNCTION stageflow.reject_editorial_derivation_mutation();
CREATE TRIGGER editorial_derivation_command_immutable BEFORE UPDATE OR DELETE
    ON stageflow.editorial_derivation_command FOR EACH ROW
    EXECUTE FUNCTION stageflow.reject_editorial_derivation_mutation();
CREATE TRIGGER editorial_candidate_provenance_immutable BEFORE UPDATE OR DELETE
    ON stageflow.editorial_candidate_provenance FOR EACH ROW
    EXECUTE FUNCTION stageflow.reject_editorial_derivation_mutation();
CREATE TRIGGER editorial_derived_candidate_immutable BEFORE UPDATE OR DELETE
    ON stageflow.editorial_candidate_moment FOR EACH ROW WHEN (OLD.origin = 'derived')
    EXECUTE FUNCTION stageflow.reject_editorial_derivation_mutation();

-- Deferred because candidate and provenance are inserted together in one transaction.
CREATE FUNCTION stageflow.check_editorial_candidate_provenance() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    candidate stageflow.editorial_candidate_moment%ROWTYPE;
    provenance stageflow.editorial_candidate_provenance%ROWTYPE;
BEGIN
    SELECT * INTO candidate FROM stageflow.editorial_candidate_moment
        WHERE candidate_moment_id = NEW.candidate_moment_id;
    SELECT * INTO provenance FROM stageflow.editorial_candidate_provenance
        WHERE candidate_moment_id = NEW.candidate_moment_id;
    IF candidate.origin = 'derived' THEN
        IF provenance.candidate_moment_id IS NULL OR NOT EXISTS (
            SELECT 1 FROM stageflow.editorial_derivation_run r
            JOIN stageflow.transcript_evidence_revision t
              ON t.evidence_id = provenance.transcript_evidence_id
            JOIN stageflow.media_timing_evidence m
              ON m.evidence_id = provenance.timing_evidence_id
            WHERE r.run_id = provenance.run_id AND r.session_id = candidate.session_id
              AND candidate.candidate_moment_id = ANY(r.candidate_ids)
              AND t.evidence_revision = provenance.transcript_revision
              AND t.evidence_status = 'complete'
              AND m.evidence_revision = provenance.timing_revision
              AND m.qualification_status = provenance.timing_qualification
        ) THEN
            RAISE EXCEPTION 'derived candidate requires matching provenance' USING ERRCODE = '23514';
        END IF;
    ELSIF provenance.candidate_moment_id IS NOT NULL THEN
        RAISE EXCEPTION 'declared candidate cannot carry derived provenance' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE CONSTRAINT TRIGGER editorial_candidate_requires_provenance
    AFTER INSERT OR UPDATE ON stageflow.editorial_candidate_moment
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION stageflow.check_editorial_candidate_provenance();
CREATE CONSTRAINT TRIGGER editorial_provenance_requires_derived_candidate
    AFTER INSERT ON stageflow.editorial_candidate_provenance
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION stageflow.check_editorial_candidate_provenance();

INSERT INTO stageflow.schema_migration(version) VALUES ('0019_derived_editorial_candidates');
