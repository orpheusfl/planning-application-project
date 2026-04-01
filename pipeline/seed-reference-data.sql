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
INSERT INTO council (council_name) VALUES
    ('Tower Hamlets');




COMMIT;
