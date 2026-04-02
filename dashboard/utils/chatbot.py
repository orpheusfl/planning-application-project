"""
Chatbot interface for the Streamlit dashboard.

Provides UI components and logic for multi-type question answering
with conversation history management stored locally in the dashboard.
Communicates with a Lambda function backend for generating responses.
"""

import streamlit as st
import requests
import json
import time
from typing import Optional, Any
import logging
import numpy as np

logger = logging.getLogger(__name__)


def _convert_to_native_python(obj: Any) -> Any:
    """Convert numpy/pandas types to native Python types for JSON serialization.

    Args:
        obj: Object to convert

    Returns:
        The object converted to a JSON-serializable type
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: _convert_to_native_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_to_native_python(item) for item in obj]
    return obj


class ChatbotInterface:
    """Manages chatbot UI and conversation history in Streamlit.

    Stores conversation history locally while calling a Lambda backend
    for generating responses.
    """

    QUESTION_TYPES = {
        "Specific application": "application",
        "Appealing a specific application": "appeal",
        "General Planning": "general",
    }

    # Async polling: check every N seconds, give up after MAX_ATTEMPTS checks
    POLL_INTERVAL_SECONDS: int = 3
    POLL_MAX_ATTEMPTS: int = 100  # 100 × 3 s = 5 minutes maximum wait

    def __init__(self, lambda_endpoint: Optional[str] = None):
        """Initialize the chatbot interface.

        Args:
            lambda_endpoint: The URL of the Lambda function endpoint.
                           If None, uses mock responses for local development.
        """
        self.lambda_endpoint = lambda_endpoint + "/ask" if lambda_endpoint else None

        self._status_base = lambda_endpoint + "/status" if lambda_endpoint else None

        self._initialize_session_state()

    def _initialize_session_state(self) -> None:
        """Initialize Streamlit session state for chatbot."""
        if "chatbot_question_type" not in st.session_state:
            st.session_state.chatbot_question_type = "general"
        if "chatbot_history_general" not in st.session_state:
            st.session_state.chatbot_history_general = []
        if "chatbot_history_application" not in st.session_state:
            st.session_state.chatbot_history_application = []
        if "chatbot_history_appeal" not in st.session_state:
            st.session_state.chatbot_history_appeal = []

    def _get_current_history(self) -> list:
        """Get the conversation history for the current question type."""
        question_type = st.session_state.chatbot_question_type
        return st.session_state[f"chatbot_history_{question_type}"]

    def _set_current_history(self, history: list) -> None:
        """Update the conversation history for the current question type."""
        question_type = st.session_state.chatbot_question_type
        st.session_state[f"chatbot_history_{question_type}"] = history

    def _handle_question_type_change(self, new_type: str) -> None:
        """Handle when the user changes the question type.

        Args:
            new_type: The new question type key
        """
        if new_type != st.session_state.chatbot_question_type:
            st.session_state.chatbot_question_type = new_type
            st.rerun()

    def _dispatch_request(self, payload: dict) -> str:
        """POST the question payload to /ask and return the job_id.

        The Lambda dispatcher returns 202 immediately with a job_id;
        the actual RAG work happens asynchronously on the Lambda side.

        Args:
            payload: The question payload to send to the Lambda

        Returns:
            The job_id string for use with _poll_for_result
        """
        response = requests.post(
            self.lambda_endpoint,
            json=payload,
            timeout=30,  # 30 s is more than enough for a dispatch-only call
        )
        response.raise_for_status()
        return response.json()["job_id"]

    def _poll_for_result(self, job_id: str) -> str:
        """Poll /status/{job_id} until the job completes and return the answer.

        Checks every POLL_INTERVAL_SECONDS for up to POLL_MAX_ATTEMPTS attempts
        before giving up with a timeout message.

        Args:
            job_id: The job identifier returned by _dispatch_request

        Returns:
            The response text, or an error message if the job failed / timed out
        """
        status_url = f"{self._status_base}/{job_id}"

        for attempt in range(self.POLL_MAX_ATTEMPTS):
            time.sleep(self.POLL_INTERVAL_SECONDS)

            poll_response = requests.get(status_url, timeout=10)
            poll_response.raise_for_status()
            data = poll_response.json()

            status = data.get("status")

            if status == "complete":
                return data.get("response", "No response from server")

            if status == "error":
                error_msg = data.get("error", "Unknown error")
                logger.error(f"RAG job {job_id} failed: {error_msg}")
                return f"Error processing request: {error_msg}"

            logger.debug(f"Job {job_id} still pending (attempt {attempt + 1})")

        return "Error: Request timed out waiting for a response. Please try again."

    def _get_response(
        self,
        user_question: str,
        application_id: Optional[str] = None,
    ) -> str:
        """Dispatch a question to the Lambda backend and poll for the result.

        Uses an async pattern to avoid the API Gateway 29-second hard timeout:
          1. POST to /ask  → receives a job_id immediately (202)
          2. Poll GET /status/{job_id} until the result is ready

        Args:
            user_question: The user's question
            application_id: Optional application ID for specific questions

        Returns:
            The response text from the completed Lambda job
        """
        question_type = st.session_state.chatbot_question_type
        history = self._get_current_history()

        payload = {
            "question_type": question_type,
            "user_question": user_question,
            "history": history,
        }

        if application_id:
            payload["application_id"] = str(application_id)

        # Convert numpy/pandas types to native Python types for JSON serialization
        payload = _convert_to_native_python(payload)

        logger.info(f"Dispatching async request to: {self.lambda_endpoint}")

        try:
            job_id = self._dispatch_request(payload)
            logger.info(f"Job dispatched, polling for result: job_id={job_id}")
            return self._poll_for_result(job_id)

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error from backend: {e}")
            return f"Error: Backend returned {e.response.status_code}. Please try again."
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timed out: {e}")
            return "Error: Request timed out. Please try again."
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to {self.lambda_endpoint}: {e}")
            return f"Error: Could not connect to backend at {self.lambda_endpoint}."
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return f"Error: {e}"
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return f"Error: {e}"

    def render(self, application_id: Optional[str] = None) -> None:
        """Render the chatbot interface.

        Args:
            application_id: Optional default application ID for application/appeal questions
        """
        st.subheader("Planning Chatbot")

        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            selected_label = next(
                label
                for label, key in self.QUESTION_TYPES.items()
                if key == st.session_state.chatbot_question_type
            )
            st.selectbox(
                "Question Nature",
                options=list(self.QUESTION_TYPES.keys()),
                index=list(self.QUESTION_TYPES.keys()).index(selected_label),
                on_change=lambda: self._handle_question_type_change(
                    self.QUESTION_TYPES[st.session_state.temp_question_type]
                ),
                key="temp_question_type",
            )

        # Show application ID input for application and appeal questions
        current_question_type = st.session_state.chatbot_question_type
        if current_question_type in ["application", "appeal"]:
            with col2:
                input_app_id = st.text_input(
                    "Application ID (can be found by checking applications in the map)",
                    value=str(application_id) if application_id else "",
                    placeholder="Enter application ID",
                    key="chatbot_app_id_input",
                )
                application_id = input_app_id if input_app_id else None

        with col3:
            if st.button("Clear History", use_container_width=True):
                self._set_current_history([])
                st.rerun()

        st.divider()

        history = self._get_current_history()

        for message in history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_input := st.chat_input("Ask a question..."):
            # Validate application ID for application/appeal questions
            if current_question_type in ["application", "appeal"]:
                if not application_id:
                    st.error(
                        "Please enter an Application ID for this question type.")
                    return

            history = self._get_current_history()

            with st.spinner("Getting response..."):
                response = self._get_response(user_input, application_id)

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            self._set_current_history(history)
            st.rerun()

    def render_in_dialog(self, application_id: Optional[str] = None) -> None:
        """Render the chatbot inside a dialog popup.

        Uses st.text_input + button instead of st.chat_input
        since chat_input is not supported inside st.dialog.

        Args:
            application_id: Optional default application ID
        """
        selected_label = next(
            label
            for label, key in self.QUESTION_TYPES.items()
            if key == st.session_state.chatbot_question_type
        )
        st.selectbox(
            "Question Nature",
            options=list(self.QUESTION_TYPES.keys()),
            index=list(self.QUESTION_TYPES.keys()).index(selected_label),
            on_change=lambda: self._handle_question_type_change(
                self.QUESTION_TYPES[st.session_state.temp_question_type_dlg]
            ),
            key="temp_question_type_dlg",
        )

        current_question_type = st.session_state.chatbot_question_type
        if current_question_type in ["application", "appeal"]:
            input_app_id = st.text_input(
                "Application ID",
                value=str(application_id) if application_id else "",
                placeholder="Enter application ID",
                key="chatbot_app_id_dlg",
            )
            application_id = input_app_id if input_app_id else None

        # Chat history
        history = self._get_current_history()
        chat_container = st.container(height=200)
        with chat_container:
            for message in history:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Input — form allows Enter to submit
        with st.form("chat_form", clear_on_submit=True, enter_to_submit=True):
            user_input = st.text_input(
                "Message",
                placeholder="Ask a question...",
                key="chatbot_dialog_input",
                label_visibility="collapsed",
            )
            send_col, clear_col, spacer = st.columns([2, 3, 2])
            with send_col:
                submitted = st.form_submit_button(
                    "Send", use_container_width=True)
            with clear_col:
                clear_clicked = st.form_submit_button(
                    "Clear History", use_container_width=True)

        if clear_clicked:
            self._set_current_history([])
            st.rerun()

        if submitted and user_input:
            if current_question_type in ["application", "appeal"] and not application_id:
                st.error("Please enter an Application ID.")
                return

            with st.spinner("Getting response..."):
                response = self._get_response(user_input, application_id)

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            self._set_current_history(history)
            st.rerun()
