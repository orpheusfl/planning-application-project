# Security Group for the Fargate Task
resource "aws_security_group" "ecs_pipeline_sg" {
  name        = "c22-planning-pipeline-task-sg"
  description = "Security group for the C22 planning pipeline task"
  vpc_id      = data.aws_vpc.c22_vpc.id

  # Outbound access: Allows the task to scrape the internet and talk to RDS
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Basic Trust Policy for ECS
data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# --- TASK EXECUTION ROLE (Pulls images, reads secrets, writes logs) ---
resource "aws_iam_role" "ecs_execution_role" {
  name               = "c22-pipeline-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_policy" "ecs_secrets_policy" {
  name        = "c22-pipeline-secrets-policy"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.pipeline-db-creds.arn,
          aws_secretsmanager_secret.pipeline-llm-api-key.arn 
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_secrets_attachment" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = aws_iam_policy.ecs_secrets_policy.arn
}

# --- TASK ROLE (Used by the app inside the container) ---
resource "aws_iam_role" "ecs_task_role" {
  name               = "c22-pipeline-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

# --- EVENTBRIDGE ROLE (Allows EventBridge to run the ECS task) ---
data "aws_iam_policy_document" "eventbridge_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eventbridge_ecs_role" {
  name               = "c22-eventbridge-ecs-role"
  assume_role_policy = data.aws_iam_policy_document.eventbridge_assume_role.json
}

resource "aws_iam_role_policy" "eventbridge_ecs_policy" {
  name = "c22-eventbridge-run-task"
  role = aws_iam_role.eventbridge_ecs_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["ecs:RunTask"]
        Resource = ["${aws_ecs_task_definition.c22-planning-pipeline-task-definition.arn_without_revision}:*"]
      },
      {
        Effect = "Allow"
        Action = ["iam:PassRole"]
        Resource = [
          aws_iam_role.ecs_execution_role.arn,
          aws_iam_role.ecs_task_role.arn
        ]
      }
    ]
  })
}

resource "aws_ecs_task_definition" "c22-planning-pipeline-task-definition" {
  family                   = "c22-planning-pipeline"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"

  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = aws_ecr_repository.c22-planning-pipeline.name
      image     = "${aws_ecr_repository.c22-planning-pipeline.repository_url}:latest"
      essential = true

      environment = [
        { name = "DB_HOST", value = aws_db_instance.pipeline-planning-db.address },
        { name = "DB_PORT", value = tostring(aws_db_instance.pipeline-planning-db.port) },
        { name = "DB_NAME", value = aws_db_instance.pipeline-planning-db.db_name },
        { name = "AWS_REGION", value = data.aws_region.current.name },
        { name = "APPLICATION_FACT_TABLE", value = var.application_fact_table },
        { name = "COUNCIL_DIM_TABLE", value = var.council_dim_table },
        { name = "STATUS_DIM_TABLE", value = var.status_dim_table },
        { name = "APPLICATION_TYPE_DIM_TABLE", value = var.application_type_dim_table }
     
      ]

      secrets = [
        { name = "DB_USER", valueFrom = "${aws_secretsmanager_secret.pipeline-db-creds.arn}:username::" },
        { name = "DB_PASSWORD", valueFrom = "${aws_secretsmanager_secret.pipeline-db-creds.arn}:password::" },
        { name = "OPENAI_API_KEY", valueFrom = "${aws_secretsmanager_secret.pipeline-llm-api-key.arn}:api_key::" }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs-pipeline.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# The Schedule (e.g., run every day at 2:00 AM UTC)
resource "aws_cloudwatch_event_rule" "pipeline_schedule" {
  name                = "c22-planning-pipeline-schedule"
  description         = "Triggers the C22 planning pipeline daily"
  schedule_expression = "cron(0 2 * * ? *)" 
}

# The Target (The ECS Task)
resource "aws_cloudwatch_event_target" "ecs_task_target" {
  rule      = aws_cloudwatch_event_rule.pipeline_schedule.name
  target_id = "run-c22-pipeline"
  arn       = aws_ecs_cluster.c22-planning-cluster.arn
  role_arn  = aws_iam_role.eventbridge_ecs_role.arn

  ecs_target {
    task_definition_arn = aws_ecs_task_definition.c22-planning-pipeline-task-definition.arn
    launch_type         = "FARGATE"

    # CRITICAL: Network config sits here now!
    network_configuration {
      subnets          = data.aws_subnets.public_subnets.ids
      security_groups  = [aws_security_group.ecs_pipeline_sg.id]
      assign_public_ip = true # Still required to scrape the internet from a public subnet
    }
  }
}
