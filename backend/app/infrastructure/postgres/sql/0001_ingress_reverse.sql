DROP TABLE IF EXISTS stageflow.production_event_ingress;
DELETE FROM stageflow.schema_migration WHERE version = '0001_ingress';
