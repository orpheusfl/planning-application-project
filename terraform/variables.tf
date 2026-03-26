variable "vpc_id" {
  description = "The ID of the VPC where the ECS cluster will be deployed"
  type        = string
  default     = "vpc-03f0d39570fbaa750"
}

variable "rds_username" {
  description = "Username for the RDS database"
  type        = string
  default     = "planning_admin"
}

variable "dashboard_container_image" {
  description = "Container image URI for the dashboard"
  type        = string
}

variable "dashboard_port" {
  description = "Port the dashboard runs on"
  type        = number
}

variable "rds_database" {
  description = "Name of the RDS database"
  type        = string
  default     = "planning_db"
}

variable "rds_port" {
  description = "Port for the RDS database"
  type        = number
  default     = 5432
}

variable "lambda_container_image" {
  description = "Container image URI for the Lambda pipeline function"
  type        = string
}

variable "rds_password" {
  description = "Password for the RDS database - should be provided from .env file"
  type        = string
  sensitive   = true
}

