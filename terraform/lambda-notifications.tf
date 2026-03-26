# ============================================================================
# Notification Lambda - Weekly notification service
# ============================================================================

# Security Group for Notification Lambda
resource "aws_security_group" "c22-planning-notifications-lambda-sg" {
  name        = "c22-planning-notifications-lambda-sg"
  description = "Security group for C22 Planning Notifications Lambda"
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
    description = "Allow Lambda to reach AWS services (Secrets Manager, SES)"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow DNS (UDP)"
  }

  egress {
    from_port   = 53
    to_port     = 53
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow DNS (TCP)"
  }

  tags = {
    Name = "c22-planning-notifications-lambda-sg"
  }
}

# CloudWatch Log Group for Notification Lambda
resource "aws_cloudwatch_log_group" "notifications-lambda" {
  name              = "/aws/lambda/c22-planning-notifications"
  retention_in_days = 30

  tags = {
    Name = "c22-planning-notifications-logs"
  }
}

# IAM role for Notification Lambda
resource "aws_iam_role" "lambda-notifications-role" {
  name               = "c22-planning-lambda-notifications-role"
  assume_role_policy = data.aws_iam_policy_document.lambda-assume-role-policy.json
}

# IAM policy for CloudWatch Logs
resource "aws_iam_role_policy" "lambda-notifications-logs-policy" {
  name   = "c22-planning-lambda-notifications-logs-policy"
  role   = aws_iam_role.lambda-notifications-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.notifications-lambda.arn}:*"
      }
    ]
  })
}

# IAM policy for ECR access
resource "aws_iam_role_policy" "lambda-notifications-ecr-policy" {
  name   = "c22-planning-lambda-notifications-ecr-policy"
  role   = aws_iam_role.lambda-notifications-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken"
        ]
        Resource = aws_ecr_repository.c22-planning-notifications.arn
      }
    ]
  })
}

# IAM policy for Secrets Manager access
resource "aws_iam_role_policy" "lambda-notifications-secrets-policy" {
  name   = "c22-planning-lambda-notifications-secrets-policy"
  role   = aws_iam_role.lambda-notifications-role.id

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

# IAM policy for VPC access
resource "aws_iam_role_policy" "lambda-notifications-vpc-policy" {
  name   = "c22-planning-lambda-notifications-vpc-policy"
  role   = aws_iam_role.lambda-notifications-role.id

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

# IAM policy for SES access (placeholder - will be used when email sending is implemented)
resource "aws_iam_role_policy" "lambda-notifications-ses-policy" {
  name   = "c22-planning-lambda-notifications-ses-policy"
  role   = aws_iam_role.lambda-notifications-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSESAccess"
        Effect = "Allow"
        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda function for notifications
resource "aws_lambda_function" "c22-planning-notifications" {
  function_name = "c22-planning-notifications"
  role           = aws_iam_role.lambda-notifications-role.arn
  memory_size    = 256
  timeout        = 300

  image_uri   = "${aws_ecr_repository.c22-planning-notifications.repository_url}:latest"
  package_type = "Image"

  vpc_config {
    subnet_ids         = data.aws_subnets.pipeline-private-subnets.ids
    security_group_ids = [aws_security_group.c22-planning-notifications-lambda-sg.id]
  }

  environment {
    variables = {
      SECRET_NAME    = aws_secretsmanager_secret.pipeline-db-creds.name
      AWS_REGION_NAME = data.aws_region.current.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda-notifications-logs-policy,
    aws_iam_role_policy.lambda-notifications-ecr-policy,
    aws_iam_role_policy.lambda-notifications-secrets-policy,
    aws_iam_role_policy.lambda-notifications-vpc-policy,
    aws_cloudwatch_log_group.notifications-lambda
  ]

  tags = {
    Name = "c22-planning-notifications"
  }
}
