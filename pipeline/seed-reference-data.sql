-- seed-reference-data.sql
-- ============================================================================
-- Populates the four reference/lookup tables that the ingestion pipeline and
-- dashboard depend on.  Must be run AFTER rds-init.sql creates the schema and
-- BEFORE any application data is inserted (foreign key constraints).
-- Usage:
--   psql -h <host> -U <user> -d <dbname> -f seed-reference-data.sql
--
-- Re-run whenever new councils, statuses, application types, or document
-- types are added to the system.
-- ============================================================================

BEGIN;

-- ==========================================================================
-- 1. Councils
-- ==========================================================================
INSERT INTO council (council_id, council_name) VALUES
    ('Tower Hamlets')
ON CONFLICT (council_id) DO NOTHING;

-- ==========================================================================
-- 2. Status types
-- ==========================================================================
INSERT INTO status_type (status_type_id, status_type) VALUES
    ('Appeal Decided'),
    ('Appeal Lodged'),
    ('Awaiting Decision'),
    ('Decided'),
    ('Received'),
    ('Registered'),
    ('Withdrawn'),
    ('Unknown')
ON CONFLICT (status_type_id) DO NOTHING;


ON CONFLICT (application_type_id) DO NOTHING;

COMMIT;
