"""Database queries for the Planning Watchdog dashboard.

Replaces the hardcoded dummy_data module with live SQL queries against the
RDS database.  Column aliases match the names the dashboard components expect.
"""

import pandas as pd
import streamlit as st

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
        a.ai_summary        AS summary,
        a.public_interest_score,
        a.application_page_url,
        a.document_page_url
    FROM application a
    JOIN status_type st      ON a.status_type_id      = st.status_type_id
    JOIN application_type at ON a.application_type_id  = at.application_type_id
    ORDER BY a.validation_date DESC;
"""


@st.cache_data(ttl=300)
def load_applications() -> pd.DataFrame:
    """Load all planning applications from the database."""
    conn = get_connection()
    df = pd.read_sql(APPLICATIONS_SQL, conn)
    df["date"] = pd.to_datetime(df["date"])
    return df
