resource "aws_ecs_cluster" "c22-planning-cluster" {
  name = "c22-planning-cluster"

  tags = {
    Name = "c22-planning-cluster"
  }
}

resource "aws_security_group" "c22-planning-ecs-sg" {
  name        = "c22-planning-sg"
  description = "Security group for C22 Planning ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = var.dashboard_port
    to_port         = var.dashboard_port
    protocol        = "tcp"
    security_groups = [aws_security_group.c22-planning-alb-sg.id]
  }

  egress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "c22-planning-ecs-sg"
  }
}


