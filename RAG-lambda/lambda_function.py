""" A placeholder for the Lambda function that will handle the LLM calls and document data extraction.
Simulates the behavior of the Lambda function without implementing the actual logic.
Checks that the Lambda function can be invoked successfully, that the question is passed to the event, and returns a mock llm response."""

import json
from dotenv import load_dotenv
import os


def lambda_handler(event, context):

    load_dotenv()  # Load environment variables from .env file
    # Simulate processing the event and generating a response

    db_user = os.getenv("DB_USERNAME", "default_user")
    db_password = os.getenv("DB_PASSWORD", "default_password")
    db_host = os.getenv("DB_HOST", "hostnotgot")
    db_name = os.getenv("DB_NAME", "namenotgot")
    db_port = os.getenv("DB_PORT", "portnotgot")

    body = json.loads(event.get("body", "{}"))

    question = body.get("question", "No question provided") if isinstance(
        body, dict) else "Invalid body format"

    # Mock response from the LLM
    llm_response = f"Mock response for the question: '{question}'"

    return {
        'statusCode': 200,
        'body': json.dumps({
            'question': question,
            'llm_response': llm_response,
            'db_credentials': {
                'user': db_user,
                'password': db_password,
                'host': db_host,
                'name': db_name,
                'port': db_port
            }
        })
    }
