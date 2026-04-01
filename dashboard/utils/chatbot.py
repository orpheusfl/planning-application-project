"""
Chatbot interface for the Streamlit dashboard.

Provides UI components and logic for multi-type question answering
with conversation history management stored locally in the dashboard.
Communicates with a Lambda function backend for generating responses.
"""

import streamlit as st
import requests
import json
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

    def __init__(self, lambda_endpoint: Optional[str] = None):
        """Initialize the chatbot interface.

        Args:
            lambda_endpoint: The URL of the Lambda function endpoint.
                           If None, uses mock responses for local development.
        """
        self.lambda_endpoint = lambda_endpoint
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

    def _get_response(
        self,
        user_question: str,
        application_id: Optional[str] = None,
    ) -> str:
        """Get a response from the Lambda backend or mock for local development.

        Args:
            user_question: The user's question
            application_id: Optional application ID for specific questions

        Returns:
            The response text from the Lambda function or mock response
        """
        question_type = st.session_state.chatbot_question_type

        # Use mock response if no endpoint is configured

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

        logger.info(f"Sending request to Lambda endpoint: {self.lambda_endpoint}")
        logger.debug(f"Payload: {payload}")

        try:
            response = requests.post(
                self.lambda_endpoint,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Response: {data}")
            if response.status_code == 200:
                return data.get("response", "No response from server")
            else:
                error_msg = data.get("error", "Unknown error")
                return f"Error: {error_msg}"

        except requests.exceptions.Timeout as e:
            logger.error(f"Lambda request timed out: {str(e)}")
            return "Error: Request timed out. Please try again."
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Could not connect to Lambda endpoint ({self.lambda_endpoint}): {str(e)}")
            return f"Error: Could not connect to backend at {self.lambda_endpoint}. Please check the endpoint is correct."
        except requests.exceptions.RequestException as e:
            logger.error(f"Lambda request failed: {str(e)}")
            return f"Error: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return f"Error: {str(e)}"

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
                    st.error("Please enter an Application ID for this question type.")
                    return

            history = self._get_current_history()

            with st.spinner("Getting response..."):
                response = self._get_response(user_input, application_id)

            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": response})
            self._set_current_history(history)
            st.rerun()
