# Security Group for Lambda
resource "aws_security_group" "c22-planning-lambda-sg" {
  name        = "c22-planning-lambda-sg"
  description = "Security group for C22 Planning Lambda function"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow Lambda to connect to RDS"
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow Lambda to reach AWS services (S3, Secrets Manager)"
  }

  tags = {
    Name = "c22-planning-lambda-sg"
  }
}

# CloudWatch Log Group for Lambda
resource "aws_iam_role" "lambda-pipeline-role" {
  name               = "c22-planning-lambda-pipeline-role"
  assume_role_policy = data.aws_iam_policy_document.lambda-assume-role-policy.json
}

# Assume role policy for Lambda
data "aws_iam_policy_document" "lambda-assume-role-policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# IAM policy for CloudWatch Logs
resource "aws_iam_role_policy" "lambda-pipeline-logs-policy" {
  name   = "c22-planning-lambda-logs-policy"
  role   = aws_iam_role.lambda-pipeline-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.lambda-pipeline.arn}:*"
      }
    ]
  })
}

# IAM policy for Secrets Manager access
resource "aws_iam_role_policy" "lambda-pipeline-secrets-policy" {
  name   = "c22-planning-lambda-secrets-policy"
  role   = aws_iam_role.lambda-pipeline-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.pipeline-db-creds.arn
      }
    ]
  })
}

# IAM policy for VPC access (to reach RDS in private subnets)
resource "aws_iam_role_policy" "lambda-pipeline-vpc-policy" {
  name   = "c22-planning-lambda-vpc-policy"
  role   = aws_iam_role.lambda-pipeline-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowVPCAccess"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM policy for S3 access
resource "aws_iam_role_policy" "lambda-pipeline-s3-policy" {
  name   = "c22-planning-lambda-s3-policy"
  role   = aws_iam_role.lambda-pipeline-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowS3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.c22-planning-s3.arn,
          "${aws_s3_bucket.c22-planning-s3.arn}/*"
        ]
      }
    ]
  })
}

# Lambda function using Docker image from ECR
resource "aws_lambda_function" "c22-planning-pipeline" {
  function_name = "c22-planning-pipeline"
  role           = aws_iam_role.lambda-pipeline-role.arn
  memory_size    = 512
  timeout        = 900

  image_uri = var.lambda_container_image

  package_type = "Image"

  vpc_config {
    subnet_ids         = data.aws_subnets.pipeline-private-subnets.ids
    security_group_ids = [aws_security_group.c22-planning-lambda-sg.id]
  }

  environment {
    variables = {
      DATABASE_HOST = aws_db_instance.pipeline-planning-db.address
      DATABASE_PORT = tostring(aws_db_instance.pipeline-planning-db.port)
      DATABASE_NAME = aws_db_instance.pipeline-planning-db.db_name
      S3_BUCKET_NAME = aws_s3_bucket.c22-planning-s3.id
      AWS_REGION = data.aws_region.current.name
      SECRET_ARN = aws_secretsmanager_secret.pipeline-db-creds.arn
    }
  }

  depends_on = [
    aws_db_instance.pipeline-planning-db,
    aws_iam_role_policy.lambda-pipeline-secrets-policy,
    aws_iam_role_policy.lambda-pipeline-vpc-policy,
    aws_iam_role_policy.lambda-pipeline-s3-policy,
    aws_iam_role_policy.lambda-pipeline-logs-policy
  ]

  tags = {
    Name = "c22-planning-pipeline"
  }
}

# EventBridge rule to trigger Lambda on weekdays at 9 AM UTC
resource "aws_cloudwatch_event_rule" "lambda-pipeline-schedule" {
  name                = "c22-planning-pipeline-schedule"
  description         = "Trigger C22 Planning pipeline daily on weekdays"
  schedule_expression = "cron(0 9 ? * MON-FRI *)"
}

# EventBridge target to invoke Lambda
resource "aws_cloudwatch_event_target" "lambda-pipeline-target" {
  rule      = aws_cloudwatch_event_rule.lambda-pipeline-schedule.name
  target_id = "c22-planning-pipeline"
  arn       = aws_lambda_function.c22-planning-pipeline.arn
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "allow-eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.c22-planning-pipeline.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda-pipeline-schedule.arn
}
