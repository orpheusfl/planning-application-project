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
    (1, 'Tower Hamlets')
ON CONFLICT (council_id) DO NOTHING;

-- ==========================================================================
-- 2. Status types
-- ==========================================================================
INSERT INTO status_type (status_type_id, status_type) VALUES
    (1, 'Pending Decision'),
    (2, 'Under Consultation'),
    (3, 'Approved'),
    (4, 'Refused')
ON CONFLICT (status_type_id) DO NOTHING;

-- ==========================================================================
-- 4. Application types
--    Best-guess mapping from application number suffixes in mock data.
--    Edit as real portal data becomes available.
-- ==========================================================================
INSERT INTO application_type (application_type_id, application_type) VALUES
    (1, 'Full Planning'),
    (2, 'Householder'),
    (3, 'Outline'),
    (4, 'Telecommunications'),
    (5, 'Tree Works'),
    (6, 'Advertising')
ON CONFLICT (application_type_id) DO NOTHING;

COMMIT;
