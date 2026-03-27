# CloudWatch Log Group for ECS Dashboard
resource "aws_cloudwatch_log_group" "ecs-dashboard" {
  name              = "/ecs/c22-planning-dashboard"
  retention_in_days = 7

  tags = {
    Name = "c22-planning-dashboard-logs"
  }
}

# CloudWatch Log Group for Lambda Pipeline
resource "aws_cloudwatch_log_group" "lambda-pipeline" {
  name              = "/aws/lambda/c22-planning-pipeline"
  retention_in_days = 7

  tags = {
    Name = "c22-planning-pipeline-logs"
  }
}

# CloudWatch Log Group for RDS PostgreSQL
resource "aws_cloudwatch_log_group" "rds-postgres" {
  name              = "/aws/rds/instance/c22-planning-db/postgres"
  retention_in_days = 7

  tags = {
    Name = "c22-planning-rds-logs"
  }
}

# CloudWatch Log Group for ECS Pipeline
resource "aws_cloudwatch_log_group" "ecs-pipeline" {
  name              = "/ecs/c22-planning-pipeline"
  retention_in_days = 7

  tags = {
    Name = "c22-planning-pipeline-logs"
  }
}

# CloudWatch Log Group for Glue Crawler (optional, for future use)
resource "aws_cloudwatch_log_group" "glue-crawler" {
  name              = "/aws/glue/crawlers/c22-planning-crawler"
  retention_in_days = 7

  tags = {
    Name = "c22-planning-glue-logs"
  }
}
