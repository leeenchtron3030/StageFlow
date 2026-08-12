DROP TABLE IF EXISTS stageflow.media_timing_evidence_application;
DROP TABLE IF EXISTS stageflow.media_timing_derivation_input;
DROP TABLE IF EXISTS stageflow.media_timing_derivation;
DROP TABLE IF EXISTS stageflow.media_timing_observation;
DROP TABLE IF EXISTS stageflow.media_timing_evidence;

DELETE FROM stageflow.schema_migration
WHERE version = '0006_media_timing_evidence';
