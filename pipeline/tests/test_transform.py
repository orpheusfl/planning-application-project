"""Test suite for the transform utilities.

Comprehensive tests for the Application class covering:
- Pure functions (address parsing, text cleaning, date parsing)
- Functions with external dependencies (mocked: requests, Selenium, OpenAI, fitz)
- Orchestration and integration tests
- Error handling and edge cases

All tests are isolated from external services and use mocks.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from ..utilities.transform import Application


class TestFormatAddress:
    """Tests for extracting postcode and address components."""

    def test_happy_path_valid_address(self, sample_application, sample_raw_address):
        """Extract postcode and address from valid UK address."""
        result = sample_application.format_address(sample_raw_address)

        assert result['address'] == "Iceland Wharf, Iceland Road, London"
        assert result['postcode'] == "E3 2JP"

    @pytest.mark.parametrize("address,expected_postcode", [
        ("123 High Street, London SW1A 1AA", "SW1A 1AA"),
        ("10 Downing Street, Westminster, London SW1A 2AA", "SW1A 2AA"),
        ("Cambridge CB2 1TN", "CB2 1TN"),
        ("Edinburgh EH8 8DX", "EH8 8DX"),
    ])
    def test_various_valid_postcodes(self, sample_application, address, expected_postcode):
        """Extract postcodes from addresses with different formats."""
        result = sample_application.format_address(address)
        assert result['postcode'] == expected_postcode

    def test_address_missing_postcode(self, sample_application):
        """Raise ValueError when address lacks UK postcode."""
        with pytest.raises(ValueError, match="Could not extract postcode"):
            sample_application.format_address("123 High Street, London")

    def test_empty_address_string(self, sample_application):
        """Raise ValueError for empty address string."""
        with pytest.raises(ValueError, match="Could not extract postcode"):
            sample_application.format_address("")

    def test_postcode_only(self, sample_application):
        """Extract postcode even when only postcode provided."""
        result = sample_application.format_address("E3 2JP")
        assert result['postcode'] == "E3 2JP"


class TestParseValidationDateToDatetime:
    """Tests for parsing validation date strings to datetime objects."""

    def test_happy_path_valid_date_format(self, sample_application):
        """Parse valid date string to datetime object."""
        result = sample_application.parse_validation_date_to_datetime(
            "Mon 09 Jun 2025")

        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 9

    @pytest.mark.parametrize("date_str,year,month,day", [
        ("09/06/2025", 2025, 6, 9),
        ("June 9, 2025", 2025, 6, 9),
        ("9 June 2025", 2025, 6, 9),
    ])
    def test_various_date_formats(self, sample_application, date_str, year, month, day):
        """Parse dates in multiple acceptable formats."""
        result = sample_application.parse_validation_date_to_datetime(date_str)
        assert result.year == year
        assert result.month == month
        assert result.day == day

    @pytest.mark.parametrize("invalid_date", [
        "Invalid Date String",
        "2025-02-30",
    ])
    def test_invalid_date_formats(self, sample_application, invalid_date):
        """Raise exception for invalid date strings."""
        with pytest.raises((ValueError, OverflowError)):
            sample_application.parse_validation_date_to_datetime(invalid_date)


class TestCleanPdfText:
    """Tests for cleaning extracted PDF text."""

    def test_happy_path_messy_text(self, sample_application):
        """Clean text with extra whitespace and newlines."""
        messy_text = "  Some text   \n\n  with  extra  \n  whitespace  "
        result = sample_application.clean_pdf_text(messy_text)
        assert result == "Some text with extra whitespace"

    def test_empty_string(self, sample_application):
        """Handle empty text string."""
        result = sample_application.clean_pdf_text("")
        assert result == ""

    def test_already_clean_text(self, sample_application):
        """Leave already-clean text unchanged."""
        clean_text = "This is already clean"
        result = sample_application.clean_pdf_text(clean_text)
        assert result == clean_text

    def test_multiple_blank_lines(self, sample_application):
        """Remove multiple blank lines between text."""
        text = "Line 1\n\n\n\nLine 2"
        result = sample_application.clean_pdf_text(text)
        assert result == "Line 1 Line 2"

    def test_tabs_and_whitespace(self, sample_application):
        """Handle tabs and other whitespace characters."""
        text = "Line1\t\tLine2\n\nLine3"
        result = sample_application.clean_pdf_text(text)
        assert result == "Line1 Line2 Line3"


class TestBuildLlmAnalysisPrompt:
    """Tests for building prompts for LLM analysis."""

    def test_happy_path_valid_inputs(self, sample_application):
        """Build valid prompt from PDF text and description with address and postcode."""
        pdf_data = [
            {"document_type": "Planning Statement", "text": "Statement content"},
            {"document_type": "Design & Access", "text": "Design content"}
        ]

        result = sample_application.build_llm_analysis_prompt(
            pdf_data, "Description", "123 Test Street, London E3 2JP", "E3 2JP")

        assert "PLANNING STATEMENT" in result
        assert "DESIGN & ACCESS" in result
        assert "Statement content" in result
        assert "Design content" in result
        assert "summary" in result.lower()
        assert "123 Test Street, London E3 2JP" in result
        assert "postcode" in result.lower()
        assert "inline references" in result.lower() or "source:" in result.lower()

    def test_empty_pdf_text_list(self, sample_application):
        """Build prompt when PDF text list is empty."""
        result = sample_application.build_llm_analysis_prompt(
            [], "Description", "123 Test Street, London E3 2JP", "E3 2JP")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "123 Test Street, London E3 2JP" in result

    def test_single_pdf(self, sample_application):
        """Build prompt with single PDF document."""
        pdf_data = [{"document_type": "Planning", "text": "Content"}]
        result = sample_application.build_llm_analysis_prompt(
            pdf_data, "Desc", "456 Another Road, London W1A 1AA", "W1A 1AA")
        assert "PLANNING" in result
        assert "Content" in result
        assert "456 Another Road, London W1A 1AA" in result

    def test_incomplete_postcode_instructions(self, sample_application):
        """Verify prompt includes special instructions for incomplete postcodes."""
        pdf_data = [{"document_type": "Application", "text": "Details"}]
        result = sample_application.build_llm_analysis_prompt(
            pdf_data, "Description", "789 Incomplete Road, London E14", "E14")

        assert "E14" in result
        assert "incomplete" in result.lower() or "complete" in result.lower()

    def test_complete_postcode_instructions(self, sample_application):
        """Verify prompt includes verification instructions for complete postcodes."""
        pdf_data = [{"document_type": "Application", "text": "Details"}]
        result = sample_application.build_llm_analysis_prompt(
            pdf_data, "Description", "789 Complete Road, London SW1A 1AA", "SW1A 1AA")

        assert "SW1A 1AA" in result
        assert "verify" in result.lower()


class TestExtractTextFromPdf:
    """Tests for extracting text content from PDF files."""

    def test_happy_path_valid_pdf(self, sample_application):
        """Extract text content from valid PDF file."""
        pdf_path = Path(__file__).parent / "fixtures" / \
            "PA_25_00973_A1-ADDENDUM-2294022.pdf"
        result = sample_application.extract_text_from_pdf(pdf_path)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_from_multiple_pdf_files(self, sample_application):
        """Extract text from multiple PDF files in fixtures."""
        fixtures_dir = Path(__file__).parent / "fixtures"
        pdf_files = list(fixtures_dir.glob("*.pdf"))

        assert len(pdf_files) >= 2, "Need at least 2 PDF files in fixtures"

        for pdf_file in pdf_files:
            result = sample_application.extract_text_from_pdf(pdf_file)
            assert isinstance(result, str), f"Expected str for {pdf_file.name}"

    def test_extracted_text_consistency(self, sample_application):
        """Verify extracting same PDF twice yields identical text."""
        pdf_path = Path(__file__).parent / "fixtures" / \
            "PA_25_00973_A1-ADDENDUM-2294022.pdf"

        result1 = sample_application.extract_text_from_pdf(pdf_path)
        result2 = sample_application.extract_text_from_pdf(pdf_path)

        assert result1 == result2

    def test_nonexistent_pdf_raises_exception(self, sample_application):
        """Raise exception when PDF file does not exist."""
        pdf_path = Path("/tmp/nonexistent_file_12345.pdf")

        with pytest.raises(Exception):
            sample_application.extract_text_from_pdf(pdf_path)


class TestGeocodePostcode:
    """Tests for converting postcodes to coordinates."""

    @patch('pipeline.utilities.transform.requests.get')
    def test_happy_path_valid_postcode(self, mock_get, sample_application):
        """Convert valid postcode to latitude and longitude."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": 200,
            "result": {"latitude": 51.5074, "longitude": -0.1278}
        }
        mock_get.return_value = mock_response

        result = sample_application.geocode_postcode("SW1A1AA")
        assert result == (51.5074, -0.1278)

    @patch('pipeline.utilities.transform.requests.get')
    def test_invalid_postcode_returns_none(self, mock_get, sample_application):
        """Return None for invalid postcode."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": 404}
        mock_get.return_value = mock_response

        result = sample_application.geocode_postcode("INVALID123")
        assert result is None

    @patch('pipeline.utilities.transform.requests.get')
    def test_connection_error_returns_none(self, mock_get, sample_application):
        """Return None on connection error."""
        mock_get.side_effect = requests.RequestException("Connection failed")

        result = sample_application.geocode_postcode("SW1A1AA")
        assert result is None


class TestToDict:
    """Tests for converting application to dictionary format."""

    @patch('pipeline.utilities.transform.Application._process_pdfs')
    @patch('pipeline.utilities.transform.Application._process_validation_date')
    @patch('pipeline.utilities.transform.Application._process_address')
    def test_happy_path_complete_application(self, mock_address, mock_date, mock_pdfs,
                                             sample_application):
        """Convert fully processed application to dictionary."""
        sample_application.process(api_key="test_key")
        result = sample_application.to_dict()

        assert isinstance(result, dict)
        assert 'application_number' in result
        assert 'ai_summary' in result
        assert 'public_interest_score' in result

    @patch('pipeline.utilities.transform.Application._process_pdfs')
    @patch('pipeline.utilities.transform.Application._process_validation_date')
    @patch('pipeline.utilities.transform.Application._process_address')
    def test_all_required_fields_present(self, mock_address, mock_date, mock_pdfs,
                                         sample_application):
        """Verify all required fields are in output dictionary."""
        sample_application.process(api_key="test_key")
        result = sample_application.to_dict()

        required_fields = [
            'application_number', 'application_type', 'address', 'postcode',
            'lat', 'long', 'validation_date', 'status_type', 'ai_summary',
            'public_interest_score', 'application_page_url', 'document_page_url'
        ]
        for field in required_fields:
            assert field in result

    def test_field_values_match_instance_variables(self, sample_application):
        """Verify dictionary values match instance variable values."""
        sample_application.address = "Test Address"
        sample_application.postcode = "E3 2JP"
        sample_application.validation_date = datetime(2025, 6, 9)

        result = sample_application.to_dict()

        assert result['address'] == sample_application.address
        assert result['postcode'] == sample_application.postcode
        assert result['validation_date'] == sample_application.validation_date
