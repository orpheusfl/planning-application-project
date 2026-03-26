#!/bin/bash
set -e

echo "Starting database initialization..."

# =========================================================
# VARIABLES DYNAMICALLY INJECTED BY TERRAFORM
# =========================================================
export DB_HOST="c22-planning-pipeline-db.c57vkec7dkkx.eu-west-2.rds.amazonaws.com"
export DB_PORT="5432"
export DB_NAME="planningdata"
export DB_USER=""
export PGPASSWORD=""
# =========================================================

SQL_FILE="rds-init.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "Error: SQL file '$SQL_FILE' not found in the current directory!"
    exit 1
fi

echo "Connecting to $DB_HOST:$DB_PORT as $DB_USER..."

# Execute the SQL script
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

echo "Database initialization completed successfully!"
