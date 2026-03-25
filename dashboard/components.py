"""Reusable Streamlit UI components for the Planning Watchdog dashboard."""

import logging

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import pydeck as pdk

import filters
from config import (
    CSS,
    DEFAULT_MARKER_COLOR,
    MAP_STYLE,
    MAP_ZOOM,
    SCORE_COLORS,
    SCROLL_DELAY_MS,
    SCROLL_OFFSET_PX,
    SEARCH_RESULTS_LIMIT,
    STATUS_CSS_CLASSES,
    TOWER_HAMLETS_CENTER,
)
from db import get_connection
from geo import generate_circle_polygon, geocode_postcode
from subscribers import (
    deactivate_all_subscriptions,
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


def _score_pill(score) -> str:
    """Return an HTML pill for the public interest score (1–5)."""
    if pd.isna(score):
        return ""
    return f'<span class="score-pill score-{int(score)}">{int(score)}</span>'


def marker_color(score) -> list[int]:
    """Map a public interest score to an RGBA colour for map markers."""
    if pd.isna(score):
        return DEFAULT_MARKER_COLOR
    return SCORE_COLORS.get(int(score), DEFAULT_MARKER_COLOR)


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
    min_score = st.slider("Minimum interest score", 1, 5, 1)
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
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar(
    applications: pd.DataFrame,
) -> tuple[pd.DataFrame, dict | None]:
    """Render sidebar filters and return *(filtered_df, location_info)*.

    *location_info* is a dict with ``lat``, ``lon``, ``radius_miles`` when a
    postcode filter is active, otherwise ``None``.
    """
    st.sidebar.title("🏗️ Planning Watchdog")
    st.sidebar.caption("Tower Hamlets applications")

    df = applications.copy()
    location_info = None

    # Date range
    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = st.sidebar.date_input(
        "Filter by date",
        value=(min_date, max_date),
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
    min_score = st.sidebar.slider("Minimum interest score", 1, 5, 1)
    df = filters.by_min_score(df, min_score)

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

    # Clear persisted map selection when any filter changes
    filter_fingerprint = (
        date_range,
        selected_status,
        min_score,
        postcode,
        radius,
    )
    if filter_fingerprint != st.session_state.get("_filter_fingerprint"):
        st.session_state["_filter_fingerprint"] = filter_fingerprint
        st.session_state.pop("map_selected_app_id", None)
        st.session_state["_filters_changed"] = True
    else:
        st.session_state["_filters_changed"] = False

    return df, location_info


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
def render_map(df: pd.DataFrame, location_info: dict | None = None):
    """Render the pydeck map and return the selection event."""
    layers = [
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
        )
    ]

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
    else:
        center_lat = TOWER_HAMLETS_CENTER["latitude"]
        center_lon = TOWER_HAMLETS_CENTER["longitude"]
        zoom = MAP_ZOOM

    view_state = pdk.ViewState(
        latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0
    )

    tooltip = {
        "html": (
            "<b>{application_number}</b><br/>{address}<br/><i>{status}</i>"
        ),
        "style": {
            "backgroundColor": "#1F2937",
            "color": "white",
            "fontSize": "13px",
            "padding": "8px 12px",
            "borderRadius": "6px",
        },
    }

    return st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style=MAP_STYLE,
        ),
        on_select="rerun",
        selection_mode="single-object",
        key="main_map",
    )


def get_selected_from_map(event, df: pd.DataFrame) -> pd.Series | None:
    """Extract the selected application from a pydeck selection event.

    The selection is persisted in ``st.session_state`` so it survives the
    transient nature of pydeck events (they only fire on the click rerun).
    """
    # Ignore stale pydeck events when sidebar filters just changed
    filters_changed = st.session_state.get("_filters_changed", False)

    if not filters_changed and event and event.selection:
        indices = event.selection.get("indices", {}).get("applications", [])
        if indices:
            idx = indices[0]
            if idx < len(df):
                app = df.iloc[idx]
                st.session_state["map_selected_app_id"] = app[
                    "application_id"
                ]
                return app

    # Fall back to previously persisted selection
    if "map_selected_app_id" in st.session_state:
        app_id = st.session_state["map_selected_app_id"]
        match = df[df["application_id"] == app_id]
        if not match.empty:
            return match.iloc[0]
        # Application no longer in the filtered set — clear stale state
        del st.session_state["map_selected_app_id"]

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
            st.rerun()

    if query and matches.empty:
        st.caption("No applications found.")

    return None


# ---------------------------------------------------------------------------
# Application detail panel
# ---------------------------------------------------------------------------
def _scroll_to_detail(application_id: str) -> None:
    """Inject JS to auto-scroll past the map to the detail panel."""
    components.html(
        f"""<script>
            // {application_id}
            setTimeout(function() {{
                window.parent.document.querySelector('section.stMain')
                    .scrollTop = {SCROLL_OFFSET_PX};
            }}, {SCROLL_DELAY_MS});
        </script>""",
        height=0,
    )


def _render_documents(documents: pd.DataFrame) -> None:
    """Render a list of document cards with links."""
    for _, doc in documents.iterrows():
        doc_type = doc["document_type"].replace("_", " ").title()
        st.markdown(
            f"""<div class="doc-card">
                <span class="doc-type">{doc_type}</span><br/>
                <strong>{doc["document_name"]}</strong><br/>
                <a href="{doc["source_url"]}" target="_blank">
                    View original ↗</a>
                &nbsp;·&nbsp;
                <code>{doc["s3_uri"]}</code>
            </div>""",
            unsafe_allow_html=True,
        )


def render_detail(
    application: pd.Series, all_documents: pd.DataFrame
) -> None:
    """Render the full detail panel for a selected application."""
    _scroll_to_detail(application["application_id"])
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
    with col_score:
        st.markdown(
            f"**Interest** {_score_pill(application['public_interest_score'])}",
            unsafe_allow_html=True,
        )

    # Date & source link
    col_date, col_link = st.columns(2)
    with col_date:
        st.markdown(f"**Date:** {application['date'].strftime('%d %B %Y')}")
    with col_link:
        if application["source_url"]:
            st.markdown(
                f"[View on council website ↗]({application['source_url']})"
            )

    # AI summary
    st.markdown("#### Summary")
    if application["summary"]:
        st.info(application["summary"])
    else:
        st.warning("No AI summary available for this application.")

    # Notes
    if application["additional_notes"]:
        st.markdown("#### Notes")
        st.markdown(application["additional_notes"])

    # Documents
    st.markdown("#### Documents")
    docs = all_documents[
        all_documents["application_id"] == application["application_id"]
    ]
    if docs.empty:
        st.caption("No documents available.")
    else:
        _render_documents(docs)
