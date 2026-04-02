"""Lambda function for handling chatbot requests from the dashboard.

Routing modes:
  1. POST /ask (API Gateway)      → dispatcher: create a job, invoke self async, return job_id
  2. GET /status/{job_id} (API GW)→ status:     read job record from DynamoDB, return result
  3. Direct async invocation      → worker:     run the RAG pipeline, write result to DynamoDB
"""

import json
import logging
import os
import time
import uuid

from dotenv import load_dotenv
import psycopg2
import boto3

from chatbot_functions import (
    answer_application_question,
    answer_appeal_question,
    answer_general_question,
)

SECRET_NAME = "c22-planning-pipeline-db-credentials"
AWS_REGION = "eu-west-2"

# DynamoDB table for async job results (set via env var from Terraform)
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "c22-planning-rag-jobs")

# How long (seconds) a job record persists in DynamoDB before TTL expiry
JOB_TTL_SECONDS = 3600

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)


# ==========================================
# DATABASE HELPERS (unchanged)
# ==========================================

def _get_credentials() -> dict:
    """Return DB credentials, preferring Secrets Manager over .env.

    On ECS the task role provides access to Secrets Manager automatically.
    Locally, if AWS credentials aren't configured or the secret can't be
    reached, we fall back to the DB_* environment variables from .env.
    """
    logging.info("Attempting to load credentials from Secrets Manager...")
    logging.info(f"SECRET_NAME: {SECRET_NAME}, AWS_REGION: {AWS_REGION}")
    try:
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        logging.info("Loaded credentials from Secrets Manager.")
        return {
            "host": secret["host"],
            "port": secret.get("port", 5432),
            "dbname": secret["dbname"],
            "user": secret["username"],
            "password": secret["password"],
        }
    except Exception as exc:
        logging.info(
            "Secrets Manager unavailable (%s), falling back to .env.", exc)
        return {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT", 5432),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USERNAME"),
            "password": os.getenv("DB_PASSWORD"),
        }


def get_connection():
    """Return a new connection to the Postgres database."""
    creds = _get_credentials()
    logging.info(
        "Using DB credentials for user='%s', dbname='%s', host='%s', port='%s'.",
        creds.get("user"),
        creds.get("dbname"),
        creds.get("host"),
        creds.get("port"),
    )

    required_fields = ["host", "port", "dbname", "user", "password"]
    missing_fields = [
        field for field in required_fields if not creds.get(field)]

    if missing_fields:
        error_msg = (
            f"Missing database credentials: {', '.join(missing_fields)}. "
            "For local development, set DB_HOST, DB_PORT, DB_NAME, DB_USER, "
            "DB_PASSWORD in .env. For ECS, set the SECRET_NAME environment "
            "variable to access AWS Secrets Manager."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        conn = psycopg2.connect(
            host=creds["host"],
            port=creds["port"],
            dbname=creds["dbname"],
            user=creds["user"],
            password=creds["password"],
        )
        logging.info("Successfully connected to database.")
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        raise


# ==========================================
# DYNAMODB HELPERS
# ==========================================

def _store_job(job_id: str, status: str, **kwargs) -> None:
    """Write or overwrite a job record in DynamoDB.

    Args:
        job_id: Unique job identifier
        status: "pending" | "complete" | "error"
        **kwargs: Extra fields to include (response, history, error, etc.)
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    item = {
        "job_id": job_id,
        "status": status,
        # TTL lets DynamoDB auto-delete stale records after 1 hour
        "ttl": int(time.time()) + JOB_TTL_SECONDS,
        **kwargs,
    }
    table.put_item(Item=item)


def _get_job(job_id: str) -> dict:
    """Fetch a job record from DynamoDB.

    Args:
        job_id: Unique job identifier

    Returns:
        The job item dict, or an empty dict if not found
    """
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(DYNAMODB_TABLE)
    response = table.get_item(Key={"job_id": job_id})
    return response.get("Item", {})


# ==========================================
# MODE 1: DISPATCHER  (POST /ask)
# ==========================================

def _handle_dispatch(body: dict, context) -> dict:
    """Create a job record, invoke self asynchronously, and return the job_id.

    The dashboard receives a 202 immediately and polls /status/{job_id}
    rather than waiting for a synchronous response through API Gateway
    (which has a hard 29-second timeout, shorter than typical RAG jobs).

    Args:
        body: Parsed request body from the dashboard
        context: Lambda context (used to get the current function name)

    Returns:
        API Gateway response with 202 status and job_id
    """
    question_type = body.get("question_type", "general")
    user_question = body.get("user_question", "")
    application_id = body.get("application_id")

    # Validate required fields up-front so the user gets immediate feedback
    if not user_question:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "user_question is required"}),
        }

    if question_type in ["application", "appeal"] and not application_id:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {"error": "application_id is required for this question type"}
            ),
        }

    job_id = str(uuid.uuid4())

    # Mark the job as pending before firing the async worker
    _store_job(job_id, "pending")
    logger.info(f"Created job {job_id} for question_type={question_type}")

    # Payload passed to the async worker invocation
    worker_payload = {
        "job_id": job_id,
        "question_type": question_type,
        "user_question": user_question,
        "application_id": application_id,
        "history": body.get("history", []),
    }

    # Invoke this same Lambda asynchronously — it will route to _process_rag_job
    lambda_client = boto3.client("lambda", region_name=AWS_REGION)
    lambda_client.invoke(
        FunctionName=context.function_name,
        InvocationType="Event",  # async: returns immediately with status 202
        Payload=json.dumps(worker_payload).encode(),
    )
    logger.info(f"Async worker invoked for job {job_id}")

    return {
        "statusCode": 202,
        "body": json.dumps({"job_id": job_id, "status": "pending"}),
    }


# ==========================================
# MODE 2: STATUS  (GET /status/{job_id})
# ==========================================

def _handle_status(event: dict) -> dict:
    """Return the current status of a job from DynamoDB.

    Args:
        event: API Gateway event containing pathParameters

    Returns:
        API Gateway response with job status and result if complete
    """
    job_id = (event.get("pathParameters") or {}).get("job_id")

    if not job_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "job_id path parameter is required"}),
        }

    job = _get_job(job_id)

    if not job:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": f"Job {job_id} not found"}),
        }

    return {
        "statusCode": 200,
        "body": json.dumps({
            "job_id": job_id,
            "status": job.get("status"),
            "response": job.get("response"),
            "history": job.get("history"),
            "question_type": job.get("question_type"),
            "error": job.get("error"),
        }),
    }


# ==========================================
# MODE 3: WORKER  (async self-invocation)
# ==========================================

def _process_rag_job(event: dict) -> None:
    """Run the RAG pipeline and write the result to DynamoDB.

    Called when this Lambda is invoked asynchronously by _handle_dispatch.
    There is no API Gateway in this path, so the return value is unused;
    the result is communicated via the DynamoDB job record.

    Args:
        event: The worker payload built by _handle_dispatch
    """
    job_id = event.get("job_id")
    question_type = event.get("question_type", "general")
    user_question = event.get("user_question", "")
    application_id = event.get("application_id")
    history = event.get("history", [])

    logger.info(f"Processing RAG job {job_id}, question_type={question_type}")

    try:
        conn = get_connection()

        if question_type == "application":
            response_text, history = answer_application_question(
                conn, application_id, user_question, history=history
            )
        elif question_type == "appeal":
            response_text, history = answer_appeal_question(
                conn, application_id, user_question, history=history
            )
        else:  # general
            response_text, history = answer_general_question(
                user_question, history=history
            )

        logger.info(f"Completed RAG job {job_id}")
        _store_job(
            job_id,
            "complete",
            response=response_text,
            history=history,
            question_type=question_type,
        )

    except Exception as e:
        logger.error(f"Error processing RAG job {job_id}: {e}", exc_info=True)
        _store_job(job_id, "error", error=str(e))


# ==========================================
# MAIN HANDLER — routes to the correct mode
# ==========================================

def lambda_handler(event, context):
    """Route incoming events to the correct handler based on invocation type.

    Three modes:
      - POST /ask (API Gateway)      → _handle_dispatch
      - GET /status/{job_id} (API GW)→ _handle_status
      - Direct async invocation      → _process_rag_job (no return value used)
    """
    route_key = event.get("routeKey", "")

    # No routeKey means this is a direct async self-invocation from _handle_dispatch
    if not route_key:
        _process_rag_job(event)
        return

    body = json.loads(event.get("body") or "{}")

    if "POST /ask" in route_key:
        return _handle_dispatch(body, context)

    if "GET /status" in route_key:
        return _handle_status(event)

    return {
        "statusCode": 404,
        "body": json.dumps({"error": f"Unknown route: {route_key}"}),
    }
