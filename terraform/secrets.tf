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
    engine   = "postgres"
    port     = 5432
  })

  # Prevents Terraform from reverting the secret if it is updated manually in AWS
  lifecycle {
    ignore_changes = [secret_string]
  }
}

# Stores the llm api key in secrets manager
resource "aws_secretsmanager_secret" "pipeline-llm-api-key" {
  name                    = "c22-planning-pipeline-llm-api-key"
  description             = "LLM API key for the planning application pipeline"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "pipeline-llm-api-key-version" {
  secret_id     = aws_secretsmanager_secret.pipeline-llm-api-key.id
  secret_string = jsonencode({
    api_key = var.llm_api_key
  })

  # Prevents Terraform from reverting the secret if it is updated manually in AWS
  lifecycle {
    ignore_changes = [secret_string]
  }
}
