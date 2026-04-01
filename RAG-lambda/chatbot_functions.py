import os
import logging

from dotenv import load_dotenv

from extract_document_data import get_rds_connection, get_related_documents_text, get_document_page_url
from prompt import generate_client, generate_application_answer, generate_appeal_answer, generate_general_answer

load_dotenv()


def answer_application_question(conn, application_id: str, user_question: str, application_text: str = None, application_page_url: str = None, history: list[dict] = None) -> str:
    """Answers a user's question about a planning application."""
    # Get application text and page URL
    if application_text is None:
        application_text = get_related_documents_text(conn, application_id)
    if application_page_url is None:
        application_page_url = get_document_page_url(conn, application_id)

    # Generate OpenAI client
    client = generate_client()

    # Generate answer
    answer = generate_application_answer(
        client, application_text, user_question, application_page_url, history=history)

    return answer


def answer_appeal_question(conn, application_id: str, user_question: str, application_text: str = None, application_page_url: str = None, history: list[dict] = None) -> str:
    """Answers a user's question about a planning appeal."""
    # Similar to answer_application_question but fetches appeal-related data instead
    if application_text is None:
        application_text = get_related_documents_text(conn, application_id)
    if application_page_url is None:
        application_page_url = get_document_page_url(conn, application_id)

    # Generate OpenAI client
    client = generate_client()

    # Generate answer
    answer = generate_appeal_answer(
        client, application_text, user_question, application_page_url, history=history)

    return answer


def answer_general_question(user_question: str, history: list[dict] = None) -> str:
    """Answers a user's general question about planning applications and appeals."""
    # Generate OpenAI client
    client = generate_client()

    # Generate answer
    answer = generate_general_answer(client, user_question, history=history)
    return answer


def chatbot(conn, user_question: str, question_type: str, application_id: str = None, history: list[dict] = None) -> str:
    if question_type == "specific_application":
        return answer_application_question(conn, application_id, user_question, history=history)
    elif question_type == "appeal":
        return answer_appeal_question(conn, application_id, user_question, history=history)
    elif question_type == "general":
        return answer_general_question(user_question, history=history)
