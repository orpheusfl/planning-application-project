"""Database queries for the OpenPlan dashboard.

Replaces the hardcoded dummy_data module with live SQL queries against the
RDS database.  Column aliases match the names the dashboard components expect.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from .db import get_connection

BOUNDARIES_DIR = Path(__file__).parent.parent / "boundaries"

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
        CASE
            WHEN st.status_type = 'Decided' AND dt.decision_type IS NOT NULL
                THEN 'Decided - ' || dt.decision_type
            ELSE st.status_type
        END AS status,
        at.application_type  AS application_type,
        c.council_name       AS council,
        a.ai_summary        AS summary,
        a.public_interest_score,
        a.score_scale,
        a.score_disturbance,
        a.score_environment,
        a.score_housing,
        a.application_page_url,
        a.document_page_url,
        a.decided_at
    FROM application a
    JOIN status_type st      ON a.status_type_id      = st.status_type_id
    JOIN application_type at ON a.application_type_id  = at.application_type_id
    JOIN council c           ON a.council_id           = c.council_id
    LEFT JOIN decision_type dt ON a.decision_type_id   = dt.decision_type_id
    ORDER BY a.validation_date DESC;
"""

STATUS_TYPES_SQL = """
    SELECT status_type FROM status_type ORDER BY status_type;
"""


@st.cache_data(ttl=3600)
def load_status_types() -> list[str]:
    """Load all status type names from the database."""
    conn = get_connection()
    df = pd.read_sql(STATUS_TYPES_SQL, conn)
    return df["status_type"].tolist()


@st.cache_data(ttl=300)
def load_applications() -> pd.DataFrame:
    """Load all planning applications from the database."""
    conn = get_connection()
    df = pd.read_sql(APPLICATIONS_SQL, conn)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# Council boundaries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_council_boundaries(council_names: list[str]) -> dict[str, dict]:
    """Load GeoJSON boundary files for the given council names.

    Looks for ``boundaries/<council_name>.geojson`` on disk.
    Councils without a matching file are silently skipped.

    Args:
        council_names: List of council names to load boundaries for

    Returns:
        Mapping of council name to parsed GeoJSON dict
    """
    boundaries: dict[str, dict] = {}
    for name in council_names:
        path = BOUNDARIES_DIR / f"{name}.geojson"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            boundaries[name] = json.load(f)
    return boundaries
