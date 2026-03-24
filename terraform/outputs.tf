output "secret_arn" {
  description = "The ARN of the Secrets Manager secret"
  value       = aws_secretsmanager_secret.pipeline-db-creds.arn
}

output "rds_endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = aws_db_instance.pipeline-planning-db.endpoint
}

output "rds_password" {
  description = "The password for the RDS instance"
  value       = jsondecode(aws_secretsmanager_secret_version.pipeline-db-creds-version.secret_string)["password"]
  sensitive   = true
}