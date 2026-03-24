# Create a DB Subnet Group
resource "aws_db_subnet_group" "pipeline-rds-subnet-group" {
  name       = "c22-planning-pipeline-db-subnet-group"
  
  subnet_ids = data.aws_subnets.pipeline-private-subnets.ids

  tags = {
    Name = "c22-planning-pipeline-db-subnet-group"
  }
}

# Create a Security Group for the RDS instance
resource "aws_security_group" "pipeline-rds-sg" {
  name        = "c22-planning-pipeline-rds-sg"
  description = "Allow inbound PostgreSQL traffic from within the VPC"
  vpc_id      = data.aws_vpc.c22_vpc.id

  ingress {
    description = "PostgreSQL access from VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [data.aws_vpc.c22_vpc.cidr_block] 
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Create the RDS Instance
resource "aws_db_instance" "pipeline-planning-db" {
  identifier             = "c22-planning-pipeline-db"
  engine                 = "postgres"
  engine_version         = "15.4"
  instance_class         = "db.t3.micro"
  allocated_storage      = 20
  storage_type           = "gp3"
  db_name                = "planningdata"
  
  # Fetch credentials using the newly named terraform resources
  username               = jsondecode(aws_secretsmanager_secret_version.pipeline-db-creds-version.secret_string)["username"]
  password               = jsondecode(aws_secretsmanager_secret_version.pipeline-db-creds-version.secret_string)["password"]
  
  db_subnet_group_name   = aws_db_subnet_group.pipeline-rds-subnet-group.name
  vpc_security_group_ids = [aws_security_group.pipeline-rds-sg.id]
  
  publicly_accessible    = false 
  skip_final_snapshot    = true  
}

# Create the bash script dynamically with Terraform outputs for initializing the database
resource "local_file" "init_db_script" {
  filename        = "${path.module}/run_init_db.sh"
  file_permission = "0755" # Makes the script executable automatically

  content = <<-EOT
    #!/bin/bash
    set -e

    echo "Starting database initialization..."

    # =========================================================
    # VARIABLES DYNAMICALLY INJECTED BY TERRAFORM
    # =========================================================
    export DB_HOST="${aws_db_instance.pipeline-planning-db.address}"
    export DB_PORT="${aws_db_instance.pipeline-planning-db.port}"
    export DB_NAME="${aws_db_instance.pipeline-planning-db.db_name}"
    export DB_USER="${jsondecode(aws_secretsmanager_secret_version.pipeline-db-creds-version.secret_string)["username"]}"
    export PGPASSWORD="${jsondecode(aws_secretsmanager_secret_version.pipeline-db-creds-version.secret_string)["password"]}"
    # =========================================================

    SQL_FILE="init.sql"

    if [ ! -f "$SQL_FILE" ]; then
        echo "Error: SQL file '$SQL_FILE' not found in the current directory!"
        exit 1
    fi

    echo "Connecting to $DB_HOST:$DB_PORT as $DB_USER..."

    # Execute the SQL script
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SQL_FILE"

    echo "Database initialization completed successfully!"
  EOT
}