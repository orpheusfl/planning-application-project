import os
import logging
import json

import openai
from dotenv import load_dotenv
import boto3

load_dotenv()

AWS_REGION = 'eu-west-2'
SECRET_NAME = 'c22-planning-pipeline-llm-api-key'


def generate_client() -> openai.OpenAI:
    """Generates an OpenAI client using the API key from environment variables."""
    client = boto3.client("secretsmanager", region_name=AWS_REGION)
    response = client.get_secret_value(SecretId=SECRET_NAME)
    secret = json.loads(response["SecretString"])
    api_key = secret["api_key"]
    if not api_key:
        raise ValueError("LLM_API_KEY environment variable is not set.")
    return openai.OpenAI(api_key=api_key)


def generate_application_answer(client: openai.OpenAI, application_text: str, user_question: str, planning_url: str, history=None) -> str:
    '''
    Answers a user's question about a specific application
    '''
    if history == []:
        history = [{"role": "system", "content": "You are a chatbot helping users answer any questions they might have "
                    "about planning applications in the UK. Always respond in simple, plain english, and be concise. "
                    "If you don't know the answer to a question, say you don't know. You will be provided with the user's "
                    "question and the text of a planning application. Use the information in the application text and from the planning url to answer the user's question."
                    "Use the provided application text to answer the user's question."
                    "Do not attempt to answer questions outside this scope"},
                   {"role": "user", "content": f'Question: {user_question}, application url: {planning_url}, application text: {application_text}'}]
    print(f'history - {history}')
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=history
    )

    

    return response.choices[0].message.content, history


def generate_appeal_answer(client: openai.OpenAI, application_text: str, user_question: str, planning_url: str, history=None) -> str:
    '''
    Answers a user's question related to appealing a specific application
    '''
    if history == []:
        history = [{"role": "system", "content": "You are a chatbot helping users answer any questions they might have "
                    "about appealing applications for planning permission in the UK. Always respond in simple, plain english, and be concise. "
                    "If you don't know the answer to a question, say you don't know. You will be provided with the user's "
                    "question and the text of a planning appeal. Use the information in the appeal text and from the planning url to answer the user's question."
                    "Use the provided appeal text to answer the user's question."
                    "Do not attempt to answer questions outside this scope."
                    "Ensure that all information you provide is specific to the appeal in question, and the local authority handling the appeal."},
                   {"role": "user", "content": f'Question: {user_question}, appeal url: {planning_url}, application text: {application_text}'}]

    print(f'history - {history}')
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=history
    )

    

    return response.choices[0].message.content, history


def generate_general_answer(client: openai.OpenAI, user_question: str, history=None) -> str:
    '''
    Answers a user's general question about planning applications and appeals.
    '''
    if history == []:
        history = [{"role": "system", "content": "You are a chatbot helping users answer any general questions they might have "
                    "about applications for planning permission and appeals in the UK. Always respond in simple, plain english, and be concise. "
                    "If you don't know the answer to a question, say you don't know. You will be provided with the user's question. "
                    "Use your knowledge of UK planning permissions and appeals to answer the user's question. "
                    "Do not attempt to answer questions outside this scope"},
                   {"role": "user", "content": user_question}]
    response = client.chat.completions.create(
        model="gpt-5-nano",
        messages=history
    )
   
    return response.choices[0].message.content, history
