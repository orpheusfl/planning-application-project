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
                "lat": 51.5248,
                "long": -0.0345,
                "date": "2026-03-01",
                "status": "Pending Decision",
                "summary": "28-storey mixed-use tower.",
                "public_interest_score": 5,
                "additional_notes": "147 objections.",
                "source_url": "https://example.com/001",
            },
            {
                "application_id": "th-2026-002",
                "application_number": "PA/26/00089/FUL",
                "address": "42 Fournier Street, London E1 6QE",
                "lat": 51.5193,
                "long": -0.0740,
                "date": "2026-02-15",
                "status": "Pending Decision",
                "summary": "Rear extension.",
                "public_interest_score": 5,
                "additional_notes": None,
                "source_url": "https://example.com/002",
            },
            {
                "application_id": "th-2026-003",
                "application_number": "PA/26/00201/FUL",
                "address": "15 Roman Road, London E2 0HU",
                "lat": 51.5310,
                "long": -0.0512,
                "date": "2026-03-10",
                "status": "Under Consultation",
                "summary": "Change of use.",
                "public_interest_score": 4,
                "additional_notes": "23 objections.",
                "source_url": "https://example.com/003",
            },
            {
                "application_id": "th-2026-004",
                "application_number": "PA/26/00156/FUL",
                "address": "Cayley Primary School, London E14 0AG",
                "lat": 51.5127,
                "long": -0.0267,
                "date": "2026-02-28",
                "status": "Approved",
                "summary": "Modular classroom block.",
                "public_interest_score": 3,
                "additional_notes": None,
                "source_url": "https://example.com/004",
            },
            {
                "application_id": "th-2026-005",
                "application_number": "PA/26/00178/FUL",
                "address": "88 Tredegar Square, London E3 5AB",
                "lat": 51.5285,
                "long": -0.0398,
                "date": "2026-01-20",
                "status": "Refused",
                "summary": "Basement swimming pool.",
                "public_interest_score": 1,
                "additional_notes": None,
                "source_url": "https://example.com/005",
            },
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture()
def sample_documents() -> pd.DataFrame:
    """Small DataFrame mirroring the schema returned by load_documents()."""
    return pd.DataFrame(
        [
            {
                "document_id": "doc-001-01",
                "application_id": "th-2026-001",
                "document_name": "Design and Access Statement",
                "document_type": "design_statement",
                "s3_uri": "s3://bucket/th-2026-001/das.pdf",
                "source_url": "https://example.com/doc1",
            },
            {
                "document_id": "doc-001-02",
                "application_id": "th-2026-001",
                "document_name": "Environmental Impact Assessment",
                "document_type": "environmental",
                "s3_uri": "s3://bucket/th-2026-001/eia.pdf",
                "source_url": "https://example.com/doc2",
            },
            {
                "document_id": "doc-003-01",
                "application_id": "th-2026-003",
                "document_name": "Planning Statement",
                "document_type": "planning_statement",
                "s3_uri": "s3://bucket/th-2026-003/ps.pdf",
                "source_url": "https://example.com/doc3",
            },
        ]
    )


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
