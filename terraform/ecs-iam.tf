# IAM role for the ECS to pull images from ECR
data "aws_iam_policy_document" "c22-planning-ecs-assume-role-policy" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "c22-planning-ecs-role" {
  name               = "c22-planning-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.c22-planning-ecs-assume-role-policy.json
}

resource "aws_iam_role_policy_attachment" "c22-planning-ecs-role-attachment" {
  role       = aws_iam_role.c22-planning-ecs-role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM role for the ECS tasks to access Secrets Manager

resource "aws_iam_role" "c22-planning-ecs-secrets-role" {
  name               = "c22-planning-ecs-secrets-role"
  assume_role_policy = data.aws_iam_policy_document.c22-planning-ecs-assume-role-policy.json
}

resource "aws_iam_role_policy" "c22-planning-ecs-secrets-role-policy" {
  name   = "c22-planning-ecs-secrets-role-policy"
  role   = aws_iam_role.c22-planning-ecs-secrets-role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "AllowSecretsManagerAccess"
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

# IAM role to allow ecs tasks to access the S3
resource "aws_iam_role_policy" "c22-planning-execution-s3-policy" {
    name = "c22-planning-execution-s3-policy"
    role = aws_iam_role.c22-planning-ecs-role.id

    policy = jsonencode({
        Version = "2012-10-17"
        Statement = [
          {
            Effect = "Allow"
            Action = [
              "s3:GetObject",
              "s3:PutObject",
              "s3:DeleteObject",
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

resource "aws_iam_role_policy_attachment" "c22-planning-ecs-glue-policy-attachment" {
  role       = aws_iam_role.c22-planning-ecs-role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}
