"""Shared test fixtures for pipeline tests."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ..utilities.transform import Application


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture()
def mock_conn() -> MagicMock:
    """Mock psycopg2 connection with a cursor context manager."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn


@pytest.fixture()
def mock_cursor(mock_conn) -> MagicMock:
    """Shortcut to the mock cursor from mock_conn."""
    return mock_conn.cursor.return_value.__enter__.return_value


@pytest.fixture()
def sample_application_info() -> dict:
    """Sample application data matching the expected load schema."""
    return {
        "application_number": "PA/26/00142/A1",
        "validation_date": "2026-03-01",
        "address": "1-5 Burdett Road, London E3 4TN",
        "postcode": "E3 4TN",
        "lat": 51.5248,
        "long": -0.0345,
        "ai_summary": "28-storey mixed-use tower.",
        "public_interest_score": 8,
        "status_type": "Pending Decision",
        "application_type": "Advertising",
        "application_page_url": "https://example.com/001",
        "document_page_url": "https://example.com/docs/001",
    }


# ============================================================================
# ADDRESS & DATE FIXTURES
# ============================================================================


@pytest.fixture
def sample_raw_address() -> str:
    """Sample valid UK address with postcode."""
    return "Iceland Wharf, Iceland Road, London E3 2JP"


@pytest.fixture
def sample_validation_date() -> str:
    """Sample validation date in expected format."""
    return "Mon 09 Jun 2025"


# ============================================================================
# PDF FIXTURES
# ============================================================================


@pytest.fixture
def sample_pdfs() -> list[dict]:
    """Sample list of PDF metadata."""
    return [
        {
            "pdf_url": "https://development.towerhamlets.gov.uk/online-applications/files/0D7EF369DE41A10749E37876158B9790/pdf/PA_25_00973_A1-ADDENDUM-2294022.pdf",
            "document_type": "Planning Statement"
        },
        {
            "pdf_url": "https://development.towerhamlets.gov.uk/online-applications/files/6A4BC53103A5828430C02EA01F8277B2/pdf/PA_25_00973_A1-ADDENDUM___PART_1-2292216.pdf",
            "document_type": "Design & Access Statement"
        }
    ]


@pytest.fixture
def fixture_pdf_planning_statement() -> Path:
    """Path to fixture PDF: Planning Statement addendum."""
    return Path(__file__).parent / "fixtures" / "PA_25_00973_A1-ADDENDUM-2294022.pdf"


@pytest.fixture
def fixture_pdf_design_statement() -> Path:
    """Path to fixture PDF: Design & Access Statement."""
    return Path(__file__).parent / "fixtures" / "PA_25_00973_A1-ADDENDUM___PART_1-2292216.pdf"


@pytest.fixture
def fixture_pdf_image() -> Path:
    """Path to fixture PDF that is actually an image (to test OCR fallback)."""
    return Path(__file__).parent / "fixtures" / "PA_25_00973_A1-BASELINE_HABITAT_PLAN-2333039.pdf"

# ============================================================================
# APPLICATION FIXTURES
# ============================================================================


@pytest.fixture
def sample_application(sample_raw_address, sample_validation_date,
                       sample_pdfs) -> Application:
    """Sample Application instance with raw data."""
    return Application(
        application_number="PA/25/00973/A1",
        application_type="Full Planning Permission",
        description="Full planning application for the redevelopment of the site to provide non-residential floorspace/yard-space together with associated refuse stores, plant, secure cycle stores and car parking, and residential dwellings including affordable housing, together with the provision of landscaped public open space, refuse stores, plant, secure cycle stores and car parking for people with disabilities.",
        address=sample_raw_address,
        validation_date=sample_validation_date,
        status="Registered",
        pdfs=sample_pdfs
    )


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def mock_temp_dir(tmp_path) -> Path:
    """Mock temporary directory for PDF storage."""
    return tmp_path
