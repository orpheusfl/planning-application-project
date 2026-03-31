""" A placeholder for the Lambda function that will handle the LLM calls and document data extraction.
Simulates the behavior of the Lambda function without implementing the actual logic.
Checks that the Lambda function can be invoked successfully, that the question is passed to the event, and returns a mock llm response."""

import json


def lambda_handler(event, context):
    # Simulate processing the event and generating a response
    body = json.loads(event.get("body", "{}"))

    question = body.get("question", "No question provided") if isinstance(
        body, dict) else "Invalid body format"

    # Mock response from the LLM
    llm_response = f"Mock response for the question: '{question}'"

    return {
        'statusCode': 200,
        'body': json.dumps({
            'question': question,
            'llm_response': llm_response
        })
    }
