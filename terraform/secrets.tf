# Create the Secret in AWS Secrets Manager
resource "aws_secretsmanager_secret" "pipeline-db-creds" {
  name                    = "c22-planning-pipeline-db-credentials"
  description             = "Database credentials for the planning applications RDS"
  recovery_window_in_days = 0 
}

# Store the username and password as a JSON payload inside the secret
resource "aws_secretsmanager_secret_version" "pipeline-db-creds-version" {
  secret_id     = aws_secretsmanager_secret.pipeline-db-creds.id
  secret_string = jsonencode({
    username = var.rds_username
    password = var.rds_password
    db_name  = var.rds_database
    db_host  = aws_db_instance.pipeline-planning-db.address
    engine   = "postgres"
    port     = 5432
  })
}