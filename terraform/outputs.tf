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

output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = aws_lb.c22-planning-alb.dns_name
}

output "dashboard_ecr_repository_uri" {
  description = "ECR repository URI for the dashboard image"
  value       = aws_ecr_repository.c22-planning-dashboard.repository_url
}

output "pipeline_ecr_repository_uri" {
  description = "ECR repository URI for the pipeline image"
  value       = aws_ecr_repository.c22-planning-pipeline.repository_url
}


output "s3_name" {
  description = "Name of the S3 bucket"
  value       = aws_s3_bucket.c22-planning-s3.id
}