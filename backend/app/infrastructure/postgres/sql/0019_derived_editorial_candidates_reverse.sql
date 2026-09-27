DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.editorial_candidate_moment WHERE origin = 'derived')
       OR EXISTS (SELECT 1 FROM stageflow.editorial_derivation_run)
       OR EXISTS (SELECT 1 FROM stageflow.editorial_phrase_list) THEN
        RAISE EXCEPTION 'cannot reverse 0019 while derived Editorial records exist';
    END IF;
END;
$$;

DROP TRIGGER editorial_candidate_requires_provenance ON stageflow.editorial_candidate_moment;
DROP TRIGGER editorial_derived_candidate_immutable ON stageflow.editorial_candidate_moment;
DROP TABLE stageflow.editorial_candidate_provenance;
DROP FUNCTION stageflow.check_editorial_candidate_provenance();
DROP TABLE stageflow.editorial_derivation_command;
DROP TABLE stageflow.editorial_derivation_run;
DROP TABLE stageflow.editorial_phrase_list;
DROP FUNCTION stageflow.reject_editorial_derivation_mutation();
ALTER TABLE stageflow.editorial_candidate_moment
    DROP CONSTRAINT editorial_candidate_moment_kind_check,
    DROP COLUMN source_kind,
    ALTER COLUMN operation_id SET NOT NULL,
    ADD CONSTRAINT editorial_candidate_moment_origin_check CHECK (origin = 'declared'),
    ADD CONSTRAINT editorial_candidate_moment_epistemic_kind_check CHECK (epistemic_kind = 'declared'),
    ADD CONSTRAINT editorial_candidate_moment_reason_code_check CHECK (reason_code = 'human_mark_moment');
DELETE FROM stageflow.schema_migration WHERE version = '0019_derived_editorial_candidates';
