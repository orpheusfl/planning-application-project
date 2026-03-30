"""Database queries for the OpenPlan dashboard.

Replaces the hardcoded dummy_data module with live SQL queries against the
RDS database.  Column aliases match the names the dashboard components expect.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from .config import BOUNDARIES_DIR
from .db import get_connection

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

APPLICATIONS_SQL = """
    SELECT
        a.application_id,
        a.application_number,
        a.address,
        a.postcode,
        a.lat,
        a.long,
        a.validation_date   AS date,
        st.status_type      AS status,
        at.application_type  AS application_type,
        c.council_name      AS council,
        a.ai_summary        AS summary,
        a.public_interest_score,
        COALESCE(a.score_scale, 0)        AS score_scale,
        COALESCE(a.score_local_impact, 0) AS score_local_impact,
        COALESCE(a.score_controversy, 0)  AS score_controversy,
        COALESCE(a.score_environment, 0)  AS score_environment,
        COALESCE(a.score_housing, 0)      AS score_housing,
        a.application_page_url,
        a.document_page_url
    FROM application a
    JOIN status_type st      ON a.status_type_id      = st.status_type_id
    JOIN application_type at ON a.application_type_id  = at.application_type_id
    JOIN council c           ON a.council_id           = c.council_id
    ORDER BY a.validation_date DESC;
"""


@st.cache_data(ttl=300)
def load_applications() -> pd.DataFrame:
    """Load all planning applications from the database."""
    conn = get_connection()
    try:
        df = pd.read_sql(APPLICATIONS_SQL, conn)
    finally:
        conn.close()
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_council_boundaries(council_names: list[str]) -> dict:
    """Load GeoJSON boundary data for councils that have a matching file.

    Looks in the ``boundaries/`` directory for files named
    ``<council_name>.geojson``.  Only councils present in *council_names*
    and with a matching file on disk are returned.

    Adds a ``tooltip_text`` property to each feature with the council name.

    Returns a dict mapping council name → parsed GeoJSON dict.
    """
    boundaries: dict = {}
    for name in council_names:
        path = BOUNDARIES_DIR / f"{name}.geojson"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            geojson = json.load(f)

        # Add tooltip_text to each feature for display on hover
        for feature in geojson.get("features", []):
            if "properties" not in feature:
                feature["properties"] = {}
            feature["properties"]["tooltip_text"] = name

        boundaries[name] = geojson
    return boundaries
