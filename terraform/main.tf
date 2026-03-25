terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket  = "c22-planning-tf-state-12345"
    key     = "global/s3/terraform.tfstate"
    region  = "eu-west-2"
    encrypt = true
  }
}

# Configures the AWS provider and default region
provider "aws" {
  region = "eu-west-2"
}

# Fetches the current AWS region dynamically for use in other resources
data "aws_region" "current" {}

# Fetches the current AWS account ID for use in resource naming
data "aws_caller_identity" "current" {}

# Fetches the existing VPC using its Name tag
data "aws_vpc" "c22_vpc" {
  filter {
    name   = "tag:Name"
    values = ["c22-VPC"]
  }
}

# Fetches existing public subnets in the VPC using their Name tags
data "aws_subnets" "public_subnets" {
  filter {
    name   = "tag:Name"
    values = ["c22-public-subnet-*"]
  }
}

# Fetches existing private subnets in the VPC using their Name tags
data "aws_subnets" "pipeline-private-subnets" {
  filter {
    name   = "tag:Name"
    values = ["c22-private-subnet-*"]
  }
}