#!/bin/bash
set -e

echo "Starting database initialization..."

# Load environment variables from .env file
if [ -f ".env" ]; then
    echo "Loading credentials from .env file..."
    source .env
else
    echo "Error: .env file not found!"
    echo "Please create a .env file with the following variables:"
    echo "  DB_USER=<your-db-user>"
    echo "  DB_PASSWORD=<your-db-password>"
    echo "  DB_NAME=<your-db-name>"
    echo "  DB_PORT=<your-db-port>"
    exit 1
fi

# Fetch DB_HOST from Terraform output
echo "Fetching RDS endpoint from Terraform output..."
DB_HOST=$(terraform output -raw rds_endpoint | cut -d: -f1)

if [ -z "$DB_HOST" ]; then
    echo "Error: Could not fetch RDS endpoint from terraform output"
    echo "Make sure you have run 'terraform apply' successfully"
    exit 1
fi

# Validate required environment variables
if [ -z "$DB_PORT" ] || [ -z "$DB_NAME" ] || [ -z "$DB_USER" ] || [ -z "$DB_PASSWORD" ]; then
    echo "Error: Missing required environment variables in .env file"
    exit 1
fi

export PGPASSWORD="$DB_PASSWORD"

SQL_FILE="../pipeline/rds-init.sql"

if [ ! -f "$SQL_FILE" ]; then
    echo "Error: SQL file '$SQL_FILE' not found!"
    exit 1
fi

echo "Connecting to $DB_HOST:$DB_PORT as $DB_USER..."

# Execute the SQL script
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

echo "Database initialization completed successfully!"
