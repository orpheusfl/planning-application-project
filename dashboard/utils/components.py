"""Reusable Streamlit UI components for the OpenPlan dashboard."""

import logging
from datetime import datetime, timedelta

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import pydeck as pdk

from . import filters
from .config import (
    BRAND_BLUE,
    CSS,
    CLUSTER_LIST_HEADER_PX,
    CLUSTER_LIST_ITEM_PX,
    DEFAULT_MARKER_COLOR,
    LOGO_PATH,
    MAP_STYLE,
    MAP_ZOOM,
    SCORE_COLORS,
    SCROLL_DELAY_MS,
    SCROLL_OFFSET_PX,
    SEARCH_RESULTS_LIMIT,
    STATUS_CSS_CLASSES,
    SUB_SCORES,
    LONDON_CENTER,
)
from .db import get_connection
from .geo import generate_circle_polygon, geocode_postcode, geojson_bounds
from .subscribers import (
    deactivate_all_subscriptions,
    deactivate_subscriptions,
    get_active_subscriptions,
    insert_subscriber,
)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _status_badge(status: str) -> str:
    """Return an HTML badge for a planning application status."""
    css_class = "status-pending"
    for keyword, cls in STATUS_CSS_CLASSES.items():
        if keyword in status.lower():
            css_class = cls
            break
    return f'<span class="status-badge {css_class}">{status}</span>'


def _score_pill(score, text: str | None = None) -> str:
    """Return an HTML pill for the public interest score (1–10).

    If text is provided, it's displayed in the pill. Otherwise, the score is shown.
    """
    if pd.isna(score):
        return ""
    score_int = int(float(score))
    display_text = text if text else str(score_int)
    return f'<span class="score-pill score-{score_int}">{display_text}</span>'


def marker_color(score) -> list[int]:
    """Map a public interest score to an RGBA colour for map markers."""
    if pd.isna(score):
        return DEFAULT_MARKER_COLOR
    return SCORE_COLORS.get(int(score), DEFAULT_MARKER_COLOR)


def _cluster_marker_color(group: pd.DataFrame) -> list[int]:
    """Return the colour for a cluster based on the highest interest score."""
    max_score = group["public_interest_score"].max()
    return marker_color(max_score)


def build_cluster_map_data(df: pd.DataFrame) -> pd.DataFrame:
    """Group applications by postcode into one map marker per location.

    Returns a DataFrame with one row per postcode containing:
    - lat/long (mean of all applications in the cluster)
    - cluster_count (number of applications)
    - color (based on highest interest score in the cluster)
    - tooltip_text (application info for singles, count for clusters)
    - postcode
    - application_id, application_number, address, status (for single-app clusters)
    """
    if df.empty:
        return pd.DataFrame()

    clusters = []
    for postcode, group in df.groupby("postcode"):
        count = len(group)
        color = _cluster_marker_color(group)

        if count == 1:
            row = group.iloc[0]
            tooltip = (
                f"<b>{row['application_number']}</b><br/>"
                f"{row['address']}<br/>"
                f"<i>{row['status']}</i>"
            )
            clusters.append({
                "postcode": postcode,
                "lat": row["lat"],
                "long": row["long"],
                "cluster_count": 1,
                "color": color,
                "tooltip_text": tooltip,
                "application_id": row["application_id"],
            })
        else:
            tooltip = (
                f"<b>{count} applications in this area</b><br/>"
                f"{postcode}<br/>"
                f"<i>Click to view all</i>"
            )
            clusters.append({
                "postcode": postcode,
                "lat": group["lat"].mean(),
                "long": group["long"].mean(),
                "cluster_count": count,
                "color": color,
                "tooltip_text": tooltip,
                "application_id": None,
            })

    return pd.DataFrame(clusters)


# ---------------------------------------------------------------------------
# Unsubscribe helpers
# ---------------------------------------------------------------------------
def _toggle_all_unsubscribe_checkboxes(subscriber_ids: list[int]) -> None:
    """Sync individual unsubscribe checkboxes with the 'Select all' state."""
    val = st.session_state["unsub_select_all"]
    for sub_id in subscriber_ids:
        st.session_state[f"unsub_{sub_id}"] = val


# ---------------------------------------------------------------------------
# Subscribe dialog
# ---------------------------------------------------------------------------
@st.dialog("Subscribe to weekly updates")
def _show_subscribe_dialog() -> None:
    """Modal form for subscribing to weekly planning application alerts."""
    st.markdown(
        "Get a weekly email with new planning applications "
        "matching your preferences."
    )

    email = st.text_input("Email address", placeholder="you@example.com")
    postcode = st.text_input("Your postcode", placeholder="e.g. E1 4TT")
    radius = st.slider("Radius (miles)", 0.1, 2.0, 0.5, step=0.1)
    min_score = st.slider("Minimum interest score", 1, 10, 1)
    consent = st.checkbox("I agree to receive weekly email updates")

    # Check for existing subscriptions after the main form fields
    action: str | None = None
    has_existing = False

    if email and "@" in email:
        try:
            conn = get_connection()
            existing = get_active_subscriptions(conn, email)
        except Exception:
            existing = []
            logging.exception("Failed to fetch existing subscriptions")

        if existing:
            has_existing = True
            st.markdown("---")
            st.markdown("**Your active subscriptions:**")
            for sub in existing:
                st.markdown(
                    f"- {sub['postcode']} — {sub['radius_miles']} mi "
                    f"radius, min score {sub['min_interest_score']}"
                )
            action = st.radio(
                "What would you like to do?",
                ["Add another subscription", "Replace all existing"],
                index=None,
                key="subscribe_action",
            )

    # Disable subscribe until consent is given AND (no existing subs, or
    # the user has picked an action)
    can_submit = consent and (not has_existing or action is not None)

    if st.button("Subscribe", type="primary", disabled=not can_submit):
        if not email or "@" not in email:
            st.error("Please enter a valid email address.")
        elif not postcode:
            st.error("Please enter your postcode.")
        else:
            coords = geocode_postcode(postcode)
            if not coords:
                st.error("Postcode not found.")
            else:
                try:
                    conn = get_connection()
                    if action == "Replace all existing":
                        deactivate_all_subscriptions(conn, email)
                    insert_subscriber(
                        conn, email, postcode,
                        coords[0], coords[1], radius, min_score,
                    )
                    st.success(
                        f"Subscribed! You'll get weekly updates for "
                        f"{postcode.upper()} ({radius} mi radius)."
                    )
                except Exception:
                    st.error("Something went wrong. Please try again.")
                    logging.exception("Subscription failed")


# ---------------------------------------------------------------------------
# Unsubscribe dialog
# ---------------------------------------------------------------------------
@st.dialog("Manage subscriptions")
def _show_unsubscribe_dialog() -> None:
    """Modal form for viewing and removing active subscriptions."""
    email = st.text_input("Email address", placeholder="you@example.com")

    if not email or "@" not in email:
        st.caption("Enter your email to view active subscriptions.")
        return

    try:
        conn = get_connection()
        subs = get_active_subscriptions(conn, email)
    except Exception:
        st.error("Could not fetch subscriptions. Please try again.")
        logging.exception("Failed to fetch subscriptions for unsubscribe")
        return

    if not subs:
        st.info("No active subscriptions found for this email.")
        return

    st.markdown(f"**{len(subs)} active subscription(s):**")

    subscriber_ids = [sub["subscriber_id"] for sub in subs]

    st.checkbox(
        "Select all",
        key="unsub_select_all",
        on_change=_toggle_all_unsubscribe_checkboxes,
        args=(subscriber_ids,),
    )

    selected_ids: list[int] = []
    for sub in subs:
        label = (
            f"{sub['postcode']} — {sub['radius_miles']} mi radius, "
            f"min score {sub['min_interest_score']}"
        )
        checked = st.checkbox(
            label,
            key=f"unsub_{sub['subscriber_id']}",
        )
        if checked:
            selected_ids.append(sub["subscriber_id"])

    if st.button(
        "Unsubscribe",
        type="primary",
        disabled=len(selected_ids) == 0,
    ):
        try:
            conn = get_connection()
            deactivate_subscriptions(conn, selected_ids)
            count = len(selected_ids)
            st.success(
                f"Unsubscribed from {count} "
                f"subscription{'s' if count != 1 else ''}."
            )
        except Exception:
            st.error("Something went wrong. Please try again.")
            logging.exception("Unsubscribe failed")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar(
    applications: pd.DataFrame,
) -> tuple[pd.DataFrame, dict | None, str | None]:
    """Render sidebar filters and return *(filtered_df, location_info, selected_council)*.

    *location_info* is a dict with ``lat``, ``lon``, ``radius_miles`` when a
    postcode filter is active, otherwise ``None``.

    *selected_council* is the council name chosen in the sidebar, or ``None``
    when only one council exists (auto-selected).
    """
    st.sidebar.image(LOGO_PATH, width=220)
    st.sidebar.caption("Tower Hamlets planning applications")

    df = applications.copy()
    location_info = None

    # Council
    councils = sorted(applications["council"].unique().tolist())
    map_picked_council = st.session_state.get("map_selected_council")

    if len(councils) > 1:
        council_options = ["All"] + councils
        default_idx = 0
        if map_picked_council and map_picked_council in council_options:
            default_idx = council_options.index(map_picked_council)
        selected_council = st.sidebar.selectbox(
            "Council", council_options, index=default_idx,
        )
        # Keep session state in sync with the selectbox
        if selected_council and selected_council != "All":
            st.session_state["map_selected_council"] = selected_council
        else:
            st.session_state.pop("map_selected_council", None)
        df = filters.by_council(df, selected_council)
    else:
        # Single council — persist selection across reruns until cleared
        selected_council = map_picked_council

    # Date range
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    days_in_data = (max_date - min_date).days
    if days_in_data >= 30:
        default_start = (datetime.now() - timedelta(days=30)).date()
    else:
        default_start = min_date
    date_range = st.sidebar.date_input(
        "Filter by date",
        value=(default_start, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        df = filters.by_date(df, date_range[0], date_range[1])

    # Status
    statuses = ["All"] + sorted(applications["status"].unique().tolist())
    selected_status = st.sidebar.selectbox("Status", statuses)
    df = filters.by_status(df, selected_status)

    # Interest score
    min_score = st.sidebar.slider(
        "Minimum interest score", 1, 10, 1,
        help="The interest score is the average of the five micro-interest "
             "scores: Scale, Local Impact, Controversy, Environment, and "
             "Housing. Use this to filter out applications below a certain "
             "overall interest level.",
    )
    df = filters.by_min_score(df, min_score)

    # Micro-interest sub-scores
    with st.sidebar.expander("Filter by micro-interests"):
        for sub in SUB_SCORES:
            min_sub = st.slider(
                sub["label"], 1, 10, 1, key=f"sub_{sub['column']}"
            )
            if min_sub > 1:
                df = filters.by_min_sub_score(df, sub["column"], min_sub)

    # Location
    st.sidebar.markdown("---")
    postcode = st.sidebar.text_input("Postcode", placeholder="e.g. E1 4TT")
    radius = st.sidebar.slider("Radius (miles)", 0.1, 2.0, 0.5, step=0.1)

    if postcode:
        coords = geocode_postcode(postcode)
        if coords:
            df = filters.by_radius(df, coords[0], coords[1], radius)
            location_info = {
                "lat": coords[0],
                "lon": coords[1],
                "radius_miles": radius,
            }
            st.sidebar.success(
                f"Showing results within {radius} mi of {postcode.upper()}"
            )
        else:
            st.sidebar.error("Postcode not found")

    st.sidebar.markdown("---")
    st.sidebar.metric("Applications shown", len(df))

    st.sidebar.markdown("---")
    if st.sidebar.button(
        "📬 Subscribe to weekly updates", use_container_width=True
    ):
        _show_subscribe_dialog()

    if st.sidebar.button(
        "Unsubscribe",
        use_container_width=True,
        key="unsubscribe_link",
        type="tertiary",
    ):
        _show_unsubscribe_dialog()

    # Clear persisted map selection when any filter changes
    filter_fingerprint = (
        selected_council,
        date_range,
        selected_status,
        min_score,
        postcode,
        radius,
    )
    if filter_fingerprint != st.session_state.get("_filter_fingerprint"):
        st.session_state["_filter_fingerprint"] = filter_fingerprint
        st.session_state.pop("map_selected_app_id", None)
        st.session_state.pop("map_selected_postcode", None)
        st.session_state.pop("cluster_selected_app_id", None)
        st.session_state.pop("_last_map_event", None)
        st.session_state.pop("_interaction_source", None)
        st.session_state["_filters_changed"] = True
    else:
        st.session_state["_filters_changed"] = False

    return df, location_info, selected_council


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
def render_map(
    df: pd.DataFrame,
    location_info: dict | None = None,
    council_boundaries: dict | None = None,
    selected_council: str | None = None,
):
    """Render the pydeck map and return the selection event."""
    layers = []

    # Council boundary polygons — rendered beneath application markers
    if council_boundaries:
        for council_name, geojson in council_boundaries.items():
            is_selected = council_name == selected_council
            # Selected: nearly invisible fill but full-opacity border
            # Unselected: subtle fill with softer border
            fill_color = [24, 0, 173, 8] if is_selected else [24, 0, 173, 40]
            line_color = [24, 0, 173, 255] if is_selected else [
                24, 0, 173, 160]
            line_width = 3 if is_selected else 1

            layers.append(
                pdk.Layer(
                    "GeoJsonLayer",
                    data=geojson,
                    id=f"boundary-{council_name}",
                    opacity=1,
                    get_fill_color=fill_color,
                    get_line_color=line_color,
                    get_line_width=line_width,
                    line_width_min_pixels=line_width,
                    pickable=not is_selected,
                    auto_highlight=not is_selected,
                    highlight_color=[0, 0, 0, 0] if is_selected else [
                        24, 0, 173, 40],
                )
            )

    # Only show application markers when a council boundary is selected
    if selected_council and selected_council != "All":
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=df,
                id="applications",
                get_position=["long", "lat"],
                get_color="color",
                get_radius=60,
                radius_min_pixels=5,
                radius_max_pixels=15,
                pickable=True,
                auto_highlight=True,
                highlight_color=[255, 200, 0, 200],
                opacity=0.6,
            )
        )

    if location_info:
        circle_coords = generate_circle_polygon(
            location_info["lat"],
            location_info["lon"],
            location_info["radius_miles"],
        )
        layers.append(
            pdk.Layer(
                "PolygonLayer",
                data=pd.DataFrame([{"polygon": circle_coords}]),
                id="radius-circle",
                get_polygon="polygon",
                get_fill_color=[59, 130, 246, 30],
                get_line_color=[59, 130, 246, 180],
                get_line_width=2,
                line_width_min_pixels=2,
                pickable=False,
            )
        )

    if location_info:
        center_lat, center_lon, zoom = (
            location_info["lat"],
            location_info["lon"],
            14,
        )
    elif (selected_council
          and selected_council != "All"
          and council_boundaries
          and selected_council in council_boundaries):
        center_lat, center_lon, zoom = geojson_bounds(
            council_boundaries[selected_council]
        )
    else:
        center_lat = LONDON_CENTER["latitude"]
        center_lon = LONDON_CENTER["longitude"]
        zoom = MAP_ZOOM

    view_state = pdk.ViewState(
        latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0
    )

    tooltip = {
        "html": "{tooltip_text}",
        "style": {
            "backgroundColor": "#1F2937",
            "color": "white",
            "fontSize": "13px",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    }

    # Use a key that incorporates the selected council so that pydeck's
    # internal selection state is reset when the council changes.  This
    # prevents deck.gl from painting its own opaque selection highlight
    # over a boundary polygon we have already processed.
    map_key = f"main_map_{selected_council or 'none'}"

    return st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style=MAP_STYLE,
        ),
        on_select="rerun",
        selection_mode="single-object",
        key=map_key,
    )


def get_selected_from_map(
    event, cluster_df: pd.DataFrame, applications: pd.DataFrame,
) -> tuple[pd.Series | None, str | None, bool]:
    """Determine what the user clicked on the map.

    Returns ``(application, selected_postcode, is_fresh_click)``:

    * Single-app marker clicked → ``(app_series, None, True)``
    * Cluster marker clicked    → ``(None, postcode_str, True)``
    * Persisted selection        → ``(app_or_none, postcode_or_none, False)``
    * Nothing selected          → ``(None, None, False)``

    The selection is persisted in ``st.session_state`` so it survives
    the transient nature of pydeck events.
    """
    filters_changed = st.session_state.get("_filters_changed", False)

    if not filters_changed and event and event.selection:
        indices = event.selection.get("indices", {})

        # Check for council boundary click first
        for layer_id, layer_indices in indices.items():
            if layer_id.startswith("boundary-") and layer_indices:
                council_name = layer_id.removeprefix("boundary-")
                st.session_state["map_selected_council"] = council_name
                st.session_state.pop("map_selected_app_id", None)
                st.session_state.pop("map_selected_postcode", None)
                st.rerun()

        # Then check for application marker click
        app_indices = indices.get("applications", [])
        if app_indices:
            idx = app_indices[0]
            # Only treat as fresh if this is a new click, not a replayed one
            event_key = ("map_click", idx)
            already_processed = (
                st.session_state.get("_last_map_event") == event_key
            )
            if not already_processed and idx < len(cluster_df):
                st.session_state["_last_map_event"] = event_key
                st.session_state["_interaction_source"] = "map"
                clicked = cluster_df.iloc[idx]
                if clicked["cluster_count"] == 1:
                    # Single application — select it directly
                    app_id = clicked["application_id"]
                    st.session_state["map_selected_app_id"] = app_id
                    st.session_state.pop("map_selected_postcode", None)
                    match = applications[
                        applications["application_id"] == app_id
                    ]
                    if not match.empty:
                        return match.iloc[0], None, True
                else:
                    # Cluster — store the postcode
                    postcode = clicked["postcode"]
                    st.session_state["map_selected_postcode"] = postcode
                    st.session_state.pop("map_selected_app_id", None)
                    return None, postcode, True

    # Fall back to persisted single-app selection
    if "map_selected_app_id" in st.session_state:
        app_id = st.session_state["map_selected_app_id"]
        match = applications[applications["application_id"] == app_id]
        if not match.empty:
            return match.iloc[0], None, False
        del st.session_state["map_selected_app_id"]

    # Fall back to persisted cluster selection
    if "map_selected_postcode" in st.session_state:
        return None, st.session_state["map_selected_postcode"], False

    return None, None, False


def render_cluster_list(
    postcode: str, applications: pd.DataFrame,
) -> pd.Series | None:
    """Render a list of applications in a postcode cluster.

    Returns the selected application if the user clicks one,
    otherwise ``None``.
    """
    cluster_apps = applications[applications["postcode"] == postcode]
    if cluster_apps.empty:
        return None

    cluster_offset = (
        CLUSTER_LIST_HEADER_PX + CLUSTER_LIST_ITEM_PX * len(cluster_apps)
    )
    _scroll_to_detail(postcode, extra_offset=cluster_offset)
    st.markdown("---")
    st.subheader(f"📍 {len(cluster_apps)} applications in {postcode}")
    st.caption("Select an application to view details.")

    # Render all application buttons in the cluster
    for _, row in cluster_apps.iterrows():
        label = (
            f"{row['application_number']} — {row['address'][:60]}  "
            f"({row['status']})"
        )
        if st.button(
            label,
            key=f"cluster_{row['application_id']}",
            use_container_width=True,
        ):
            st.session_state["cluster_selected_app_id"] = (
                row["application_id"]
            )
            st.session_state["_interaction_source"] = "cluster"
            st.rerun()

    # Return the previously selected application (after buttons are rendered)
    if "cluster_selected_app_id" in st.session_state:
        selected_id = st.session_state["cluster_selected_app_id"]
        match = cluster_apps[
            cluster_apps["application_id"] == selected_id
        ]
        if not match.empty:
            cluster_offset = (
                CLUSTER_LIST_HEADER_PX
                + CLUSTER_LIST_ITEM_PX * len(cluster_apps)
            )
            st.session_state["_cluster_scroll_offset"] = cluster_offset
            _scroll_to_detail(selected_id, extra_offset=cluster_offset)
            return match.iloc[0]

    return None


# ---------------------------------------------------------------------------
# Search bar
# ---------------------------------------------------------------------------
def render_search_bar(
    df: pd.DataFrame, *, suppress_results: bool = False
) -> pd.Series | None:
    """Render the search bar and optionally display results.

    When *suppress_results* is ``True`` the text input is still rendered
    but matching results / buttons are hidden (used when a map selection
    is active).
    """
    st.markdown("---")
    query = st.text_input(
        "Search by application number",
        placeholder="e.g. PA/26/00142/A1",
        key="search_query",
    )

    if suppress_results:
        return None

    # Handle a previously clicked search-result button
    if "search_selected_id" in st.session_state:
        selected_id = st.session_state.pop("search_selected_id")
        st.session_state.pop("map_selected_app_id", None)
        match = df[df["application_id"] == selected_id]
        if not match.empty:
            return match.iloc[0]

    if not query:
        return None

    # Active search clears any lingering map selection
    st.session_state.pop("map_selected_app_id", None)

    matches = filters.by_application_number(df, query)

    if len(matches) == 1:
        return matches.iloc[0]

    if len(matches) > SEARCH_RESULTS_LIMIT:
        st.caption(
            f"{len(matches)} results — showing first {SEARCH_RESULTS_LIMIT}:"
        )
        matches = matches.head(SEARCH_RESULTS_LIMIT)
    elif len(matches) > 1:
        st.caption(f"{len(matches)} results found:")

    for _, row in matches.iterrows():
        if st.button(
            f"{row['application_number']} — {row['address'][:50]}",
            key=row["application_id"],
        ):
            st.session_state["search_selected_id"] = row["application_id"]
            st.session_state["_interaction_source"] = "search"
            st.rerun()

    if query and matches.empty:
        st.caption("No applications found.")

    return None


# ---------------------------------------------------------------------------
# Application detail panel
# ---------------------------------------------------------------------------
def _scroll_to_detail(anchor_id: str, extra_offset: int = 0) -> None:
    """Inject JS to auto-scroll past the map to the detail panel."""
    total_offset = SCROLL_OFFSET_PX + extra_offset
    components.html(
        f"""<script>
            // {anchor_id}
            setTimeout(function() {{
                window.parent.document.querySelector('section.stMain')
                    .scrollTop = {total_offset};
            }}, {SCROLL_DELAY_MS});
        </script>""",
        height=0,
    )


def render_detail(application: pd.Series) -> None:
    """Render the full detail panel for a selected application."""
    extra_offset = st.session_state.get("_cluster_scroll_offset", 0)
    _scroll_to_detail(application["application_id"], extra_offset=extra_offset)
    st.markdown("---")

    # Header row
    col_info, col_status, col_score = st.columns([3, 1, 1])
    with col_info:
        st.subheader(application["application_number"])
        st.caption(application["address"])
    with col_status:
        st.markdown(
            f"**Status** {_status_badge(application['status'])}",
            unsafe_allow_html=True,
        )
        if application["application_page_url"]:
            st.markdown(
                f"[View on council website ↗]({application['application_page_url']})"
            )
    with col_score:
        score = application['public_interest_score']
        st.markdown(
            f"**Interest Score** {_score_pill(score, f'{int(score)}/10')}",
            unsafe_allow_html=True,
        )

    # Date
    st.markdown(f"**Date:** {application['date'].strftime('%d %B %Y')}")

    # Sub-score breakdown
    has_sub_scores = any(
        application.get(sub["column"], 0) > 0 for sub in SUB_SCORES
    )
    if has_sub_scores:
        with st.expander("Interest score breakdown"):
            for sub in SUB_SCORES:
                raw_value = application.get(sub["column"])
                if pd.isna(raw_value) or raw_value <= 0:
                    continue
                sub_val = int(raw_value)
                st.markdown(
                    f"{sub['label']}: {_score_pill(sub_val, f'{sub_val}/10')}",
                    unsafe_allow_html=True,
                )

    # AI summary
    st.markdown("#### Summary")
    if application["summary"]:
        st.info(application["summary"])
    else:
        st.warning("No AI summary available for this application.")

    # Application documents
    st.markdown("#### Documents")
    if application["document_page_url"]:
        st.markdown(
            f"[View application documents ↗]({application['document_page_url']})"
        )
    else:
        st.caption("No document link available.")
