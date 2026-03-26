# Security Group for Application Load Balancer
resource "aws_security_group" "c22-planning-alb-sg" {
  name        = "c22-planning-alb-sg"
  description = "Security group for C22 Planning ALB"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "c22-planning-alb-sg"
  }
}

# Application Load Balancer
resource "aws_lb" "c22-planning-alb" {
  name               = "c22-planning-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.c22-planning-alb-sg.id]
  subnets            = data.aws_subnets.public_subnets.ids

  enable_deletion_protection = false

  tags = {
    Name = "c22-planning-alb"
  }
}

# Target Group for Dashboard
resource "aws_lb_target_group" "c22-planning-dashboard" {
  name        = "c22-planning-dashboard"
  port        = var.dashboard_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    interval            = 30
    path                = "/"
    matcher             = "200"
  }

  tags = {
    Name = "c22-planning-dashboard"
  }
}

# ALB Listener
resource "aws_lb_listener" "c22-planning-http" {
  load_balancer_arn = aws_lb.c22-planning-alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.c22-planning-dashboard.arn
  }
}
