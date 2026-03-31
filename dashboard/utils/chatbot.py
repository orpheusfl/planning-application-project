"""
Chatbot interface for the Streamlit dashboard.

Provides UI components and logic for multi-type question answering
with conversation history management.
"""

import streamlit as st
from typing import Optional, Callable


class ChatbotInterface:
    """Manages chatbot UI and conversation history in Streamlit."""

    QUESTION_TYPES = {
        "Application": "application",
        "Appeal": "appeal",
        "General Planning": "general",
    }

    def __init__(self):
        """Initialize the chatbot interface."""
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

    def _build_history_for_request(self, user_question: str) -> list:
        """Build the message history for an API request.

        Args:
            user_question: The user's question

        Returns:
            List of message dictionaries for the API
        """
        question_type = st.session_state.chatbot_question_type
        history = self._get_current_history()
        history.append({"role": "user", "content": user_question})
        return history

    def render(
        self,
        get_response_callback: Callable,
        application_id: Optional[str] = None,
    ) -> None:
        """Render the chatbot interface.

        Args:
            get_response_callback: Function to call to get the chatbot response.
                                  Should accept (question_type, user_question, application_id, history)
                                  and return the response string.
            application_id: Optional application ID for application/appeal questions
        """
        st.subheader("Planning Chatbot")

        col1, col2 = st.columns([3, 1])

        with col1:
            selected_label = next(
                label
                for label, key in self.QUESTION_TYPES.items()
                if key == st.session_state.chatbot_question_type
            )
            question_type = st.selectbox(
                "Question Type",
                options=list(self.QUESTION_TYPES.keys()),
                index=list(self.QUESTION_TYPES.keys()).index(selected_label),
                on_change=lambda: self._handle_question_type_change(
                    self.QUESTION_TYPES[st.session_state.temp_question_type]
                ),
                key="temp_question_type",
            )

        with col2:
            if st.button("Clear History", use_container_width=True):
                self._set_current_history([])
                st.rerun()

        st.divider()

        history = self._get_current_history()

        for message in history:
            if message["role"] == "system":
                continue
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_input := st.chat_input("Ask a question..."):
            history = self._build_history_for_request(user_input)
            question_type = st.session_state.chatbot_question_type
            response = get_response_callback(
                question_type, user_input, application_id, history
            )

            history.append({"role": "assistant", "content": response})
            self._set_current_history(history)
            st.rerun()
