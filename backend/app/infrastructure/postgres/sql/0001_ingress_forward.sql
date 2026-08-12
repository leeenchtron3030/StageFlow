CREATE SCHEMA IF NOT EXISTS stageflow;

CREATE TABLE IF NOT EXISTS stageflow.schema_migration (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stageflow.production_event_ingress (
    ingress_id uuid PRIMARY KEY,
    production_event_id uuid NOT NULL UNIQUE,
    source_namespace text NOT NULL CHECK (btrim(source_namespace) <> ''),
    source_identifier text NOT NULL CHECK (btrim(source_identifier) <> ''),
    identity_kind text NOT NULL CHECK (
        identity_kind IN ('source_event_key', 'canonical_fingerprint')
    ),
    identity_value text NOT NULL CHECK (btrim(identity_value) <> ''),
    fingerprint_version text,
    source_event_key text,
    canonical_document text NOT NULL,
    facts_digest text NOT NULL CHECK (length(facts_digest) = 64),
    event_type text NOT NULL,
    event_source text NOT NULL,
    payload jsonb NOT NULL,
    authoritative_source_facts jsonb NOT NULL,
    correlation_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    first_received_at timestamptz NOT NULL,
    last_received_at timestamptz NOT NULL,
    delivery_count bigint NOT NULL CHECK (delivery_count > 0),
    CONSTRAINT production_event_ingress_identity_unique UNIQUE (
        source_namespace, source_identifier, identity_kind, identity_value
    ),
    CONSTRAINT production_event_ingress_identity_shape CHECK (
        (identity_kind = 'source_event_key' AND source_event_key IS NOT NULL
            AND fingerprint_version IS NULL)
        OR
        (identity_kind = 'canonical_fingerprint' AND source_event_key IS NULL
            AND fingerprint_version IS NOT NULL)
    )
);

INSERT INTO stageflow.schema_migration (version)
VALUES ('0001_ingress')
ON CONFLICT (version) DO NOTHING;
