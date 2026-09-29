LOCK TABLE stageflow.boundary_cue_composition IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM stageflow.boundary_cue_composition) THEN
        RAISE EXCEPTION 'boundary_cue_reverse_requires_empty_compositions';
    END IF;
END;
$$;
DROP TABLE stageflow.boundary_cue_segment_phrase;
DROP TABLE stageflow.boundary_cue_custom_phrase;
DROP TABLE stageflow.boundary_cue_choice;
DROP TABLE stageflow.boundary_cue_group;
DROP TABLE stageflow.boundary_cue_composition;
DROP FUNCTION stageflow.boundary_cue_complete();
DROP FUNCTION stageflow.boundary_cue_immutable();
DELETE FROM stageflow.schema_migration WHERE version = '0025_boundary_cue_composition';
