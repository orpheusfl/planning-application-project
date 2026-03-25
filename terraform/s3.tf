# S3 Bucket for pipeline data
resource "aws_s3_bucket" "c22-planning-s3" {
  bucket = "c22-planning-s3"

  tags = {
    Name = "c22-planning-s3"
  }
}

# Enable versioning on the bucket
resource "aws_s3_bucket_versioning" "c22-planning-versioning" {
  bucket = aws_s3_bucket.c22-planning-s3.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block public access for security
resource "aws_s3_bucket_public_access_block" "c22-planning-public-access" {
  bucket = aws_s3_bucket.c22-planning-s3.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "c22-planning-encryption" {
  bucket = aws_s3_bucket.c22-planning-s3.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Outputs
output "s3_bucket_name" {
  value       = aws_s3_bucket.c22-planning-s3.id
  description = "Name of the S3 bucket"
}

output "s3_bucket_arn" {
  value       = aws_s3_bucket.c22-planning-s3.arn
  description = "ARN of the S3 bucket"
}