terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
provider "aws" {
  region = "eu-west-2"
}

# Ensure this is ALL LOWERCASE when you run apply
variable "bucket_name" {
  type = string
}

resource "aws_s3_bucket" "c22-planning-tf-state" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_versioning" "c22-planning-tf-state" {
  bucket = aws_s3_bucket.c22-planning-tf-state.id
  versioning_configuration {
    status = "Enabled"
  }
}

output "config_snippet" {
  value = <<EOT
  backend "s3" {
    bucket  = "${aws_s3_bucket.c22-planning-tf-state.id}"
    key     = "global/s3/terraform.tfstate"
    region  = "eu-west-2"
    encrypt = true
    # dynamodb_table removed due to permissions
  }
EOT
}