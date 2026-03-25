# Security Group for RDS
resource "aws_security_group" "c22-planning-rds-sg" {
  name        = "c22-planning-rds-sg"
  description = "Security group for C22 Planning RDS"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.c22-planning-ecs-sg.id]
    description     = "Allow ECS tasks to access RDS"
  }

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.c22-planning-lambda-sg.id]
    description     = "Allow Lambda to access RDS"
  }

  tags = {
    Name = "c22-planning-rds-sg"
  }
}

# DB Subnet Group for RDS
resource "aws_db_subnet_group" "c22-planning-db-subnet" {
  name       = "c22-planning-db-subnet-group"
  subnet_ids = data.aws_subnets.pipeline-private-subnets.ids

  tags = {
    Name = "c22-planning-db-subnet-group"
  }
}

# DB Parameter Group for PostgreSQL
resource "aws_db_parameter_group" "c22-planning-db-params" {
  family      = "postgres15"
  name        = "c22-planning-db-params"
  description = "Parameter group for C22 Planning RDS"

  tags = {
    Name = "c22-planning-db-params"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "pipeline-planning-db" {
  identifier            = "c22-planning-db"
  engine                = "postgres"
  engine_version        = "15.3"
  instance_class        = "db.t3.micro"
  allocated_storage     = 20
  storage_type          = "gp3"
  db_subnet_group_name  = aws_db_subnet_group.c22-planning-db-subnet.name
  parameter_group_name  = aws_db_parameter_group.c22-planning-db-params.name
  publicly_accessible   = false
  skip_final_snapshot   = false
  final_snapshot_identifier = "c22-planning-db-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"

  db_name  = var.rds_database
  username = var.rds_username
  password = random_password.pipeline-db-password.result
  port     = 5432

  vpc_security_group_ids = [aws_security_group.c22-planning-rds-sg.id]

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"


  tags = {
    Name = "c22-planning-db"
  }
}
