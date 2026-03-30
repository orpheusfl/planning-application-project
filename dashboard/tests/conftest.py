"""Shared fixtures for the dashboard test suite."""

from datetime import date
from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture()
def sample_applications() -> pd.DataFrame:
    """Small DataFrame mirroring the schema returned by load_applications()."""
    df = pd.DataFrame(
        [
            {
                "application_id": "th-2026-001",
                "application_number": "PA/26/00142/A1",
                "address": "1-5 Burdett Road, London E3 4TN",
                "postcode": "E3 4TN",
                "lat": 51.5248,
                "long": -0.0345,
                "date": "2026-03-01",
                "status": "Pending Decision",
                "application_type": "Advertising",
                "council": "Tower Hamlets",
                "summary": "28-storey mixed-use tower.",
                "public_interest_score": 9,
                "score_scale": 10,
                "score_local_impact": 8,
                "score_controversy": 9,
                "score_environment": 7,
                "score_housing": 10,
                "application_page_url": "https://example.com/001",
                "document_page_url": "https://example.com/docs/001",
            },
            {
                "application_id": "th-2026-002",
                "application_number": "PA/26/00089/FUL",
                "address": "42 Fournier Street, London E1 6QE",
                "postcode": "E1 6QE",
                "lat": 51.5193,
                "long": -0.0740,
                "date": "2026-02-15",
                "status": "Pending Decision",
                "application_type": "Full Planning",
                "council": "Tower Hamlets",
                "summary": "Rear extension.",
                "public_interest_score": 8,
                "score_scale": 3,
                "score_local_impact": 2,
                "score_controversy": 8,
                "score_environment": 4,
                "score_housing": 1,
                "application_page_url": "https://example.com/002",
                "document_page_url": "https://example.com/docs/002",
            },
            {
                "application_id": "th-2026-003",
                "application_number": "PA/26/00201/FUL",
                "address": "15 Roman Road, London E2 0HU",
                "postcode": "E3 4TN",
                "lat": 51.5250,
                "long": -0.0340,
                "date": "2026-03-10",
                "status": "Under Consultation",
                "application_type": "Full Planning",
                "council": "Tower Hamlets",
                "summary": "Change of use.",
                "public_interest_score": 6,
                "score_scale": 4,
                "score_local_impact": 7,
                "score_controversy": 6,
                "score_environment": 5,
                "score_housing": 3,
                "application_page_url": "https://example.com/003",
                "document_page_url": None,
            },
            {
                "application_id": "th-2026-004",
                "application_number": "PA/26/00156/FUL",
                "address": "Cayley Primary School, London E14 0AG",
                "postcode": "E14 0AG",
                "lat": 51.5127,
                "long": -0.0267,
                "date": "2026-02-28",
                "status": "Approved",
                "application_type": "Full Planning",
                "council": "Hackney",
                "summary": "Modular classroom block.",
                "public_interest_score": 3,
                "score_scale": 2,
                "score_local_impact": 5,
                "score_controversy": 1,
                "score_environment": 3,
                "score_housing": 1,
                "application_page_url": "https://example.com/004",
                "document_page_url": "https://example.com/docs/004",
            },
            {
                "application_id": "th-2026-005",
                "application_number": "PA/26/00178/FUL",
                "address": "88 Tredegar Square, London E3 5AB",
                "postcode": "E3 4TN",
                "lat": 51.5252,
                "long": -0.0342,
                "date": "2026-01-20",
                "status": "Refused",
                "application_type": "Full Planning",
                "council": "Tower Hamlets",
                "summary": "Basement swimming pool.",
                "public_interest_score": 2,
                "score_scale": 1,
                "score_local_impact": 3,
                "score_controversy": 2,
                "score_environment": 2,
                "score_housing": 1,
                "application_page_url": "https://example.com/005",
                "document_page_url": None,
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture()
def mock_db_connection():
    """Return a MagicMock that behaves like a psycopg2 connection.

    The cursor is a context-manager mock whose ``execute``, ``fetchall``,
    and ``description`` attributes can be configured per-test.
    """
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cursor
