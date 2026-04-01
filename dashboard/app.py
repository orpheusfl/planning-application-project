"""
OpenPlan — Tower Hamlets Dashboard

Streamlit dashboard for browsing planning applications in Tower Hamlets.
Displays applications on an interactive map with filtering, search,
and per-application detail views including AI summaries and documents
with an integrated chatbot for answering questions.
"""

import streamlit as st
import pandas as pd
import os

from utils.components import (
    build_cluster_map_data,
    get_selected_from_map,
    marker_color,
    render_cluster_list,
    render_detail,
    render_map,
    render_search_bar,
    render_sidebar,
)
from utils.config import CSS
from utils.queries import load_applications, load_council_boundaries
from utils.chatbot import ChatbotInterface

from dotenv import load_dotenv

load_dotenv()
# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OpenPlan — Tower Hamlets",
    page_icon="openplan-favicon.png",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def _handle_search_selection() -> None:
    """Clear map selections when user clicked a search result."""
    st.session_state.pop("map_selected_app_id", None)
    st.session_state.pop("map_selected_postcode", None)


def _show_single_app_detail(filtered_df: pd.DataFrame, selected_app: pd.Series) -> None:
    """Display a single application selected from map or search."""
    st.session_state.pop("search_selected_id", None)
    st.session_state.pop("search_query", None)
    st.session_state.pop("_cluster_scroll_offset", None)
    render_search_bar(filtered_df, suppress_results=True)
    render_detail(selected_app)


def _show_cluster_detail(filtered_df: pd.DataFrame, selected_postcode: str) -> None:
    """Display applications in a postcode cluster."""
    render_search_bar(filtered_df, suppress_results=True)
    cluster_pick = render_cluster_list(selected_postcode, filtered_df)
    if cluster_pick is not None:
        render_detail(cluster_pick)


def _show_search_results(filtered_df: pd.DataFrame) -> None:
    """Display search bar with results when no map selection."""
    st.session_state.pop("_cluster_scroll_offset", None)
    search_result = render_search_bar(filtered_df)
    if search_result is not None:
        render_detail(search_result)


def main() -> None:
    """Entry point for the OpenPlan dashboard."""
    st.markdown(CSS, unsafe_allow_html=True)

    # Get Lambda endpoint from environment
    lambda_endpoint = os.getenv("RAG_LAMBDA_ENDPOINT", "").strip()

    applications = load_applications()

    filtered_df, location_info, selected_council = render_sidebar(applications)

    # Load boundary polygons only for councils that appear in the data
    council_names = applications["council"].unique().tolist()
    council_boundaries = load_council_boundaries(council_names)

    # Render interactive map with applications plotted as colour-coded markers
    st.title("Tower Hamlets planning applications")
    cluster_df = build_cluster_map_data(filtered_df)
    event = render_map(cluster_df, location_info,
                       council_boundaries, selected_council)

    # Selection priority is determined by the last user interaction.
    # A fresh map click sets source to "map"; typing in search sets it
    # implicitly (no map/cluster source); clicking a search result sets
    # "search"; clicking a cluster item sets "cluster".
    selected_app, selected_postcode, is_fresh_click = get_selected_from_map(
        event, cluster_df, filtered_df,
    )

    source = st.session_state.get("_interaction_source")

    if source == "search":
        _handle_search_selection()
        selected_app = None
        selected_postcode = None

    if selected_app is not None:
        _show_single_app_detail(filtered_df, selected_app)
    elif selected_postcode is not None:
        _show_cluster_detail(filtered_df, selected_postcode)
    else:
        _show_search_results(filtered_df)

    # Separate chatbot tab
    st.divider()
    st.title("Planning Assistant")
    chatbot = ChatbotInterface(lambda_endpoint)
    chatbot.render()


if __name__ == "__main__":
    main()
