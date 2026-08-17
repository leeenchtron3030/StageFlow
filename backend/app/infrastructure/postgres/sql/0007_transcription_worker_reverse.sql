ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT IF EXISTS work_operation_terminal_result_fk;
ALTER TABLE stageflow.work_operation
    DROP CONSTRAINT IF EXISTS work_operation_current_attempt_fk;

DROP TABLE IF EXISTS stageflow.transcript_evidence_alignment;
DROP TABLE IF EXISTS stageflow.transcript_evidence_word;
DROP TABLE IF EXISTS stageflow.transcript_evidence_segment;
DROP TABLE IF EXISTS stageflow.transcript_evidence_revision;
DROP TABLE IF EXISTS stageflow.work_operation_attempt;
DROP TABLE IF EXISTS stageflow.work_operation;
DROP TABLE IF EXISTS stageflow.work_worker_presence;
DROP TABLE IF EXISTS stageflow.work_worker_capability;
DROP TABLE IF EXISTS stageflow.work_worker;

DELETE FROM stageflow.schema_migration
WHERE version = '0007_transcription_worker';

