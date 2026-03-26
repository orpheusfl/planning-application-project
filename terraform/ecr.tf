# ECR Repository for Dashboard
resource "aws_ecr_repository" "c22-planning-dashboard" {
  name                 = "c22-planning-dashboard"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "c22-planning-dashboard"
  }
}

# Lifecycle policy for Dashboard (keep last 5 images)
resource "aws_ecr_lifecycle_policy" "c22-planning-dashboard-lifecycle" {
  repository = aws_ecr_repository.c22-planning-dashboard.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# ECR Repository for Pipeline
resource "aws_ecr_repository" "c22-planning-pipeline" {
  name                 = "c22-planning-pipeline"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "c22-planning-pipeline"
  }
}

# Lifecycle policy for Pipeline (keep last 5 images)
resource "aws_ecr_lifecycle_policy" "c22-planning-pipeline-lifecycle" {
  repository = aws_ecr_repository.c22-planning-pipeline.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
