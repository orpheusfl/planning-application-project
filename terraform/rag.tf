# ==========================================
# 1. ECR REPOSITORY
# ==========================================

resource "aws_ecr_repository" "rag_lambda_repo" {
  name                 = "c22-planning-rag-repo"
  image_tag_mutability = "MUTABLE"
  
  # Scans your docker images for vulnerabilities on push
  image_scanning_configuration {
    scan_on_push = true
  }
}

# ==========================================
# 2. IAM ROLE & POLICIES
# ==========================================

resource "aws_iam_role" "rag_lambda_role" {
  name = "c22-planning-rag-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# Grants standard permissions for the Lambda to write logs to CloudWatch
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.rag_lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ==========================================
# 3. LAMBDA FUNCTION (DOCKER CONTAINER)
# ==========================================

resource "aws_lambda_function" "rag_lambda" {
  function_name = "c22-planning-rag-lambda"
  role          = aws_iam_role.rag_lambda_role.arn
  
  # Instructs AWS to use a Docker container instead of a .zip file
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.rag_lambda_repo.repository_url}:latest"
  
  timeout       = 60 
  memory_size   = 1024 # Increased for heavier RAG/Vector processing

  # No vpc_config block is included, giving the Lambda default 
  # outbound internet access to reach the LLM and the public RDS.

  environment {
    variables = {
      # Injected plaintext variables for load_dotenv() to pick up
      DB_USERNAME = var.rds_username
      DB_PASSWORD = var.rds_password
      LLM_API_KEY = var.llm_api_key
    }
  }
}

# ==========================================
# 4. API GATEWAY
# ==========================================

resource "aws_apigatewayv2_api" "rag_api" {
  name          = "c22-planning-rag-api"
  protocol_type = "HTTP"
  description   = "API endpoint to trigger the RAG Lambda container"

  # Enables web frontends to interact with this API
  cors_configuration {
    allow_origins = ["*"] 
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_integration" "rag_api_integration" {
  api_id                 = aws_apigatewayv2_api.rag_api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.rag_lambda.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "rag_api_route" {
  api_id    = aws_apigatewayv2_api.rag_api.id
  route_key = "POST /ask"
  target    = "integrations/${aws_apigatewayv2_integration.rag_api_integration.id}"
}

resource "aws_apigatewayv2_stage" "rag_api_stage" {
  api_id      = aws_apigatewayv2_api.rag_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw_invoke_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rag_lambda.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rag_api.execution_arn}/*/*"
}

# ==========================================
# 5. OUTPUTS
# ==========================================

output "rag_api_endpoint" {
  description = "The endpoint URL to send questions to your RAG Lambda"
  value       = "${aws_apigatewayv2_api.rag_api.api_endpoint}/ask"
}

output "ecr_repository_url" {
  description = "The URL of the ECR repository to push your Docker image to"
  value       = aws_ecr_repository.rag_lambda_repo.repository_url
}