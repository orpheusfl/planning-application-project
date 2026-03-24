# Configures Terraform, required providers, and the S3 backend for remote state


resource "aws_s3_bucket" "c22-planning-s3" {
  bucket = "c22-planning-s3"
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

# IAM user for Python scripts
resource "aws_iam_user" "c22-planning-user" {
  name = "c22-planning-s3-user"
}

# IAM access key for programmatic access
resource "aws_iam_access_key" "c22-planning-key" {
  user = aws_iam_user.c22-planning-user.name
}

# IAM policy for S3 access
resource "aws_iam_user_policy" "c22-planning-s3-policy" {
  name   = "c22-planning-s3-policy"
  user   = aws_iam_user.c22-planning-user.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.c22-planning-s3.arn,
          "${aws_s3_bucket.c22-planning-s3.arn}/*"
        ]
      }
    ]
  })
}

# Outputs for use in Python scripts
output "s3_bucket_name" {
  value       = aws_s3_bucket.c22-planning-s3.id
  description = "Name of the S3 bucket"
}

output "aws_access_key_id" {
  value       = aws_iam_access_key.c22-planning-key.id
  description = "AWS Access Key ID for S3 access"
  sensitive   = true
}

output "aws_secret_access_key" {
  value       = aws_iam_access_key.c22-planning-key.secret
  description = "AWS Secret Access Key for S3 access"
  sensitive   = true
}