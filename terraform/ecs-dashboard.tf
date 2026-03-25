# ECS Task Definition for the C22 Planning Dashboard
resource "aws_ecs_task_definition" "c22-planning-dashboard" {
  family                   = "c22-planning-dashboard"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.c22-planning-ecs-secrets-role.arn
  task_role_arn            = aws_iam_role.c22-planning-ecs-role.arn

  container_definitions = jsonencode([
    {
      name      = "c22-planning-dashboard"
      image     = var.dashboard_container_image
      essential = true

      portMappings = [
        {
          containerPort = var.dashboard_port
          hostPort      = var.dashboard_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "DATABASE_HOST"
          value = aws_db_instance.pipeline-planning-db.address
        },
        {
          name  = "DATABASE_PORT"
          value = tostring(aws_db_instance.pipeline-planning-db.port)
        },
        {
          name  = "DATABASE_NAME"
          value = aws_db_instance.pipeline-planning-db.db_name
        },
        {
          name  = "S3_BUCKET_NAME"
          value = aws_s3_bucket.c22-planning-s3.id
        },
        {
          name  = "AWS_REGION"
          value = data.aws_region.current.name
        }
      ]

      secrets = [
        {
          name      = "DATABASE_USERNAME"
          valueFrom = "${aws_secretsmanager_secret.pipeline-db-creds.arn}:username::"
        },
        {
          name      = "DATABASE_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.pipeline-db-creds.arn}:password::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs-dashboard.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# ECS Service for the Dashboard
resource "aws_ecs_service" "c22-planning-dashboard" {
  name            = "c22-planning-dashboard"
  cluster         = aws_ecs_cluster.c22-planning-cluster.id
  task_definition = aws_ecs_task_definition.c22-planning-dashboard.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.pipeline-private-subnets.ids
    security_groups  = [aws_security_group.c22-planning-ecs-sg.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.c22-planning-dashboard.arn
    container_name   = "c22-planning-dashboard"
    container_port   = var.dashboard_port
  }

  depends_on = [
    aws_db_instance.pipeline-planning-db,
    aws_iam_role_policy.c22-planning-ecs-secrets-role-policy,
    aws_iam_role_policy.c22-planning-execution-s3-policy
  ]
}
