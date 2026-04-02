# Infrastructure — OpenPlan (Terraform)

All AWS infrastructure for OpenPlan is defined as code using Terraform. A single `terraform apply` provisions the complete environment.

---

## AWS Resources Provisioned

| Resource | Service | Description |
|---|---|---|
| `ecs-pipeline.tf` | ECS Fargate | Scheduled task running the ETL pipeline |
| `ecs-dashboard.tf` | ECS Fargate | Long-running service hosting the Streamlit dashboard |
| `alb.tf` | Application Load Balancer | Public HTTPS endpoint for the dashboard |
| `rds.tf` | RDS PostgreSQL | Primary database (private subnet) |
| `pipeline-rds.tf` | RDS | Pipeline-specific RDS security group and access rules |
| `s3.tf` | S3 | Bucket for storing planning application PDFs |
| `rag.tf` | Lambda | RAG chatbot Lambda function and API Gateway |
| `ecr.tf` | ECR | Container registries for pipeline, dashboard, and Lambda images |
| `secrets.tf` | Secrets Manager | Stores database credentials; injected into ECS task definitions |
| `ecs-iam.tf` | IAM | Roles and policies for ECS tasks and Lambda |
| `cloudwatch.tf` | CloudWatch | Log groups and alarms |

**Region:** eu-west-2 (London)  
**State backend:** S3 with encryption enabled

---

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate permissions
- Docker (for building container images before `apply`)
- An existing VPC (`c22-VPC`) with public and private subnets

---

## Deploying

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Fill in rds_password, container image URIs, and any other required values

terraform init
terraform plan
terraform apply
```

---

## Key Variables (`terraform.tfvars`)

| Variable | Description |
|---|---|
| `rds_password` | Master password for the RDS instance (sensitive) |
| `rds_username` | Database admin username (default: `planning_admin`) |
| `rds_database` | Database name (default: `planning_db`) |
| `dashboard_container_image` | ECR URI for the dashboard container |
| `dashboard_port` | Port the dashboard Streamlit app listens on |

See [`variables.tf`](variables.tf) for the full list with descriptions and defaults.

---

## Outputs

After `terraform apply`, run `terraform output` to retrieve:

- Dashboard ALB DNS name
- RDS endpoint
- ECR repository URLs
- API Gateway URL for the RAG Lambda

---

## State Management

Remote state is stored in S3 (`c22-planning-tf-state-12345`) with encryption. Run the bootstrap configuration in [`../terraform-bootstrap/`](../terraform-bootstrap/main.tf) once to create this bucket before the first `terraform init`.
