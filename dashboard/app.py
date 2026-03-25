"""
Planning Watchdog — Tower Hamlets Dashboard

Streamlit dashboard for browsing planning applications in Tower Hamlets.
Displays applications on an interactive map with filtering, search,
and per-application detail views including AI summaries and documents.
"""

import streamlit as st

from utils.components import (
    get_selected_from_map,
    marker_color,
    render_detail,
    render_map,
    render_search_bar,
    render_sidebar,
)
from utils.config import CSS
from utils.queries import load_applications, load_documents

# ---------------------------------------------------------------------------
# Page config — must be the first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Planning Watchdog — Tower Hamlets",
    page_icon="🏗️",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """Entry point for the Planning Watchdog dashboard."""
    st.markdown(CSS, unsafe_allow_html=True)

    applications = load_applications()
    documents = load_documents()

    filtered_df, location_info = render_sidebar(applications)

    # Map
    st.title("Tower Hamlets planning applications")
    map_df = filtered_df.copy()
    map_df["color"] = map_df["public_interest_score"].apply(marker_color)
    event = render_map(map_df, location_info)

    # Selection: map click takes priority over search
    selected_app = get_selected_from_map(event, map_df)

    if selected_app is not None:
        # Map selection active — show search bar but suppress results
        st.session_state.pop("search_selected_id", None)
        if st.session_state.get("search_query"):
            st.session_state["search_query"] = ""
        render_search_bar(filtered_df, suppress_results=True)
        render_detail(selected_app, documents)
    else:
        # No map selection — show search bar with results
        search_result = render_search_bar(filtered_df)
        if search_result is not None:
            render_detail(search_result, documents)


if __name__ == "__main__":
    main()
