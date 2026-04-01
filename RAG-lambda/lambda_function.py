"""Lambda function for handling chatbot requests from the dashboard.

Receives question type, user question, and conversation history,
then routes to the appropriate chatbot function.
"""

import json
import logging
import os

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

load_dotenv()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

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
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }


def get_connection():
    """Return a new connection to the Postgres database."""
    creds = _get_credentials()
    #ssl_cert = os.getenv("DB_SSL_CERT", "./global-bundle.pem")
    logging.info(
        "Using DB credentials for user='%s', dbname='%s', host='%s', port='%s'.",
        creds.get("user"),
        creds.get("dbname"),
        creds.get("host"),
        creds.get("port"),
    )

    # Validate credentials before attempting connection
    required_fields = ["host", "port", "dbname", "user", "password"]
    missing_fields = [field for field in required_fields
                      if not creds.get(field)]

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

def lambda_handler(event, context):
    """Handle chatbot requests from the dashboard.
    
    Expected request body:
    {
        "question_type": "application" | "appeal" | "general",
        "user_question": "The user's question",
        "application_id": "app_id" (required for application/appeal),
        "history": [{"role": "user"|"assistant", "content": "..."}, ...]
    }
    """
    try:
        body = json.loads(event.get("body", "{}"))

        question_type = body.get("question_type", "general")
        user_question = body.get("user_question", "")
        application_id = body.get("application_id")
        history = body.get("history", [])

        if not user_question:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "user_question is required"}),
            }

        # Get database connection
        conn = get_connection()
        response_text = None

        if question_type == "application":
            if not application_id:
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {"error": "application_id is required for application questions"}
                    ),
                }
            response_text, _ = answer_application_question(
                conn, application_id, user_question, history=history
            )
        elif question_type == "appeal":
            if not application_id:
                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {"error": "application_id is required for appeal questions"}
                    ),
                }
            response_text, _ = answer_appeal_question(
                conn, application_id, user_question, history=history
            )
        else:  # general
            response_text, _ = answer_general_question(user_question, history=history)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "response": response_text,
                "question_type": question_type,
            }),
        }

    except Exception as e:
        logger.error(f"Error processing chatbot request: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Internal server error: {str(e)}"}),
        }
