"""
Planning Watchdog — Tower Hamlets Dashboard

Streamlit dashboard for browsing planning applications in Tower Hamlets.
Displays applications on an interactive map with filtering, search,
and per-application detail views including AI summaries and documents.
"""

import streamlit as st

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
from utils.queries import load_applications

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

    filtered_df, location_info = render_sidebar(applications)

    # Render interactive map with applications plotted as colour-coded markers
    st.title("Tower Hamlets planning applications")
    cluster_df = build_cluster_map_data(filtered_df)
    event = render_map(cluster_df, location_info)

    # Selection priority is determined by the last user interaction.
    # A fresh map click sets source to "map"; typing in search sets it
    # implicitly (no map/cluster source); clicking a search result sets
    # "search"; clicking a cluster item sets "cluster".
    selected_app, selected_postcode, is_fresh_click = get_selected_from_map(
        event, cluster_df, filtered_df,
    )

    source = st.session_state.get("_interaction_source")

    if source == "search":
        # User last clicked a search result — search wins
        selected_app = None
        selected_postcode = None
        st.session_state.pop("map_selected_app_id", None)
        st.session_state.pop("map_selected_postcode", None)

    if selected_app is not None:
        # Single application selected — show detail directly
        st.session_state.pop("search_selected_id", None)
        st.session_state.pop("_cluster_scroll_offset", None)
        render_search_bar(filtered_df, suppress_results=True)
        render_detail(selected_app)
    elif selected_postcode is not None:
        # Cluster selected — show list of applications in this postcode
        render_search_bar(filtered_df, suppress_results=True)
        cluster_pick = render_cluster_list(selected_postcode, filtered_df)
        if cluster_pick is not None:
            render_detail(cluster_pick)
    else:
        # No map selection — show search bar with results
        st.session_state.pop("_cluster_scroll_offset", None)
        search_result = render_search_bar(filtered_df)
        if search_result is not None:
            render_detail(search_result)


if __name__ == "__main__":
    main()
