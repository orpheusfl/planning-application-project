#!/bin/bash
# Script to check RDS database size

# Get RDS endpoint from Terraform output
RDS_ENDPOINT=$(terraform -chdir=terraform output -raw rds_endpoint | cut -d: -f1)
RDS_USER="planning_admin"
RDS_DB="planning_db"
RDS_PORT="5432"

# Read password (you'll be prompted)
read -sp "Enter RDS password: " RDS_PASSWORD
echo ""

# Connect to PostgreSQL and get database sizes
psql -h "$RDS_ENDPOINT" -U "$RDS_USER" -d "$RDS_DB" -p "$RDS_PORT" << EOF
-- Overall database size
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = '$RDS_DB';

-- Size per table
\echo ''
\echo 'Size per table:'
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Size per index
\echo ''
\echo 'Size per index:'
SELECT 
    schemaname,
    indexname,
    pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) AS size
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_relation_size(schemaname||'.'||indexname) DESC;
EOF
