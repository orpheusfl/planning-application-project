"""Test suite for the transform utilities.

Comprehensive tests for the Application class covering:
- Pure functions (address parsing, text cleaning, date parsing)
- Functions with external dependencies (mocked: requests, Selenium, OpenAI, fitz)
- Orchestration and integration tests
- Error handling and edge cases
- Parallel LLM call dispatch and result merging

All tests are isolated from external services and use mocks.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from ..utilities.transform import Application
from ..utilities.config import SUB_SCORE_RUBRICS


class TestFormatAddress:
    """Tests for extract_postcode_from_address and format_address_by_removing_postcode."""

    def test_happy_path_valid_address(self, sample_raw_address):
        """Extract postcode and address from valid UK address."""

        postcode = Application.extract_postcode_from_address(
            sample_raw_address)
        address = Application.format_address_by_removing_postcode(
            sample_raw_address, postcode)

        assert address == "Iceland Wharf, Iceland Road, London"
        assert postcode == "E3 2JP"

    @pytest.mark.parametrize("address,expected_postcode", [
        ("123 High Street, London SW1A 1AA", "SW1A 1AA"),
        ("10 Downing Street, Westminster, London SW1A 2AA", "SW1A 2AA"),
        ("Cambridge CB2 1TN", "CB2 1TN"),
        ("Edinburgh EH8 8DX", "EH8 8DX"),
    ])
    def test_various_valid_postcodes(self, address, expected_postcode):
        """Extract postcodes from addresses with different formats."""
        result = Application.extract_postcode_from_address(address)
        assert result == expected_postcode

    def test_address_missing_postcode(self):
        """Return empty string when address lacks a UK postcode."""
        result = Application.extract_postcode_from_address(
            "123 High Street, London")
        assert result == ""

    def test_empty_address_string(self):
        """Return empty string for empty address input."""
        result = Application.extract_postcode_from_address("")
        assert result == ""

    def test_postcode_only(self):
        """Extract postcode even when only postcode provided."""
        result = Application.extract_postcode_from_address("E3 2JP")
        assert result == "E3 2JP"


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


class TestBuildSummaryPrompt:
    """Tests for _build_summary_prompt."""

    def test_happy_path_valid_inputs(self, sample_application):
        """Build valid prompt from PDF text and description with address and postcode."""
        prompt = sample_application._build_summary_prompt(
            "PLANNING STATEMENT:\nStatement content\n\nDESIGN & ACCESS:\nDesign content",
            "Description",
            "123 Test Street, London E3 2JP",
            "The postcode 'E3 2JP' appears complete.",
        )

        assert "PLANNING STATEMENT" in prompt
        assert "DESIGN & ACCESS" in prompt
        assert "Statement content" in prompt
        assert "Design content" in prompt
        assert "summary" in prompt.lower()
        assert "123 Test Street, London E3 2JP" in prompt
        assert "postcode" in prompt.lower()
        assert "inline references" in prompt.lower() or "source:" in prompt.lower()

    def test_empty_pdf_text(self, sample_application):
        """Build prompt when PDF text is empty."""
        prompt = sample_application._build_summary_prompt(
            "", "Description", "123 Test Street, London E3 2JP", "instructions")
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "123 Test Street, London E3 2JP" in prompt

    def test_single_pdf(self, sample_application):
        """Build prompt with single PDF document text."""
        prompt = sample_application._build_summary_prompt(
            "PLANNING:\nContent",
            "Desc",
            "456 Another Road, London W1A 1AA",
            "instructions",
        )
        assert "PLANNING" in prompt
        assert "Content" in prompt
        assert "456 Another Road, London W1A 1AA" in prompt

    def test_incomplete_postcode_instructions(self, sample_application):
        """Verify prompt includes special instructions for incomplete postcodes."""
        instructions = sample_application._get_postcode_instructions("E14")
        prompt = sample_application._build_summary_prompt(
            "PDF TEXT", "Description", "789 Incomplete Road, London E14", instructions)

        assert "E14" in prompt
        assert "incomplete" in prompt.lower() or "complete" in prompt.lower()

    def test_complete_postcode_instructions(self, sample_application):
        """Verify prompt includes verification instructions for complete postcodes."""
        instructions = sample_application._get_postcode_instructions(
            "SW1A 1AA")
        prompt = sample_application._build_summary_prompt(
            "PDF TEXT", "Description", "789 Complete Road, London SW1A 1AA", instructions)

        assert "SW1A 1AA" in prompt
        assert "verify" in prompt.lower()

    def test_does_not_include_sub_scores(self, sample_application):
        """Summary prompt should not request sub-score fields."""
        prompt = sample_application._build_summary_prompt(
            "PDF", "Desc", "Addr", "instructions")
        assert "score_disturbance" not in prompt
        assert "score_scale" not in prompt
        assert "score_housing" not in prompt
        assert "score_environment" not in prompt


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
            'public_interest_score', 'score_disturbance', 'score_scale',
            'score_housing', 'score_environment',
            'application_page_url', 'document_page_url',
            'decision_type', 'decided_at', 'database_action',
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

    def test_decision_type_and_decided_at_in_output(self, sample_application):
        """Verify decision_type and decided_at are populated when set on the instance."""
        sample_application.decision = "Refused"
        sample_application.decision_date = "Mon 09 Jun 2025"

        result = sample_application.to_dict()

        assert result['decision_type'] == "Refused"
        assert isinstance(result['decided_at'], datetime)

    def test_decided_at_is_none_when_no_decision_date(self, sample_application):
        """Verify decided_at is None when decision_date is not set."""
        sample_application.decision_date = None

        result = sample_application.to_dict()

        assert result['decided_at'] is None

    def test_database_action_in_output(self, sample_application):
        """Verify database_action is correctly passed through to the output dict."""
        sample_application.database_action = "Update"

        result = sample_application.to_dict()

        assert result['database_action'] == "Update"


# ============================================================================
# PARALLEL LLM ANALYSIS TESTS
# ============================================================================


class TestCallLlm:
    """Tests for _call_llm (single LLM call)."""

    def test_returns_parsed_json(self, sample_application):
        """Valid JSON response is parsed and returned as a dict."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"score_scale": 3}'
        mock_client.chat.completions.create.return_value = mock_response

        result = sample_application._call_llm(
            mock_client, "system msg", "user prompt"
        )
        assert result == {"score_scale": 3}

    def test_raises_on_invalid_json(self, sample_application):
        """Raise ValueError when the LLM returns non-JSON."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json at all"
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid JSON"):
            sample_application._call_llm(
                mock_client, "system msg", "user prompt"
            )


class TestAnalysePdfTextParallel:
    """Tests for the parallelised analyse_pdf_text method."""

    def _make_mock_client(self, responses: dict[str, str]) -> MagicMock:
        """Create a mock OpenAI client that returns different JSON per call.

        Args:
            responses: Mapping of JSON response strings to return in order
        """
        mock_client = MagicMock()
        side_effects = []
        for json_str in responses.values():
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = json_str
            side_effects.append(mock_resp)

        mock_client.chat.completions.create.side_effect = side_effects
        return mock_client

    @patch.object(Application, '_setup_openai_client')
    def test_merges_all_five_results(self, mock_setup, sample_application):
        """Five parallel calls merge into the expected return schema."""
        responses = {
            "summary": '{"summary": "A big tower.", "postcode": "E3 2JP"}',
            "score_disturbance": '{"score_disturbance": 4}',
            "score_scale": '{"score_scale": 5}',
            "score_housing": '{"score_housing": 3}',
            "score_environment": '{"score_environment": 2}',
        }
        mock_setup.return_value = self._make_mock_client(responses)

        pdf_data = [{"document_type": "Application Form", "text": "Content"}]
        result = sample_application.analyse_pdf_text(pdf_data, "fake-key")

        assert result['ai_summary'] == "A big tower."
        assert result['postcode'] == "E3 2JP"
        assert result['score_disturbance'] == 4
        assert result['score_scale'] == 5
        assert result['score_housing'] == 3
        assert result['score_environment'] == 2
        assert result['public_interest_score'] == round((4 + 5 + 3 + 2) / 4)

    @patch.object(Application, '_setup_openai_client')
    def test_return_schema_matches_original(self, mock_setup, sample_application):
        """Return dict has exactly the expected keys."""
        responses = {
            "summary": '{"summary": "Summary.", "postcode": "SW1A 1AA"}',
            "score_disturbance": '{"score_disturbance": 1}',
            "score_scale": '{"score_scale": 1}',
            "score_housing": '{"score_housing": 1}',
            "score_environment": '{"score_environment": 1}',
        }
        mock_setup.return_value = self._make_mock_client(responses)

        pdf_data = [{"document_type": "Form", "text": "text"}]
        result = sample_application.analyse_pdf_text(pdf_data, "fake-key")

        expected_keys = {
            'ai_summary', 'public_interest_score',
            'score_scale', 'score_disturbance',
            'score_environment', 'score_housing', 'postcode',
        }
        assert set(result.keys()) == expected_keys

    @patch.object(Application, '_setup_openai_client')
    def test_public_interest_score_is_average(self, mock_setup, sample_application):
        """public_interest_score is the rounded mean of the four sub-scores."""
        responses = {
            "summary": '{"summary": "S", "postcode": "E1 1AA"}',
            "score_disturbance": '{"score_disturbance": 2}',
            "score_scale": '{"score_scale": 3}',
            "score_housing": '{"score_housing": 4}',
            "score_environment": '{"score_environment": 5}',
        }
        mock_setup.return_value = self._make_mock_client(responses)

        pdf_data = [{"document_type": "Form", "text": "t"}]
        result = sample_application.analyse_pdf_text(pdf_data, "fake-key")

        assert result['public_interest_score'] == round((2 + 3 + 4 + 5) / 4)

    @patch.object(Application, '_setup_openai_client')
    def test_makes_five_api_calls(self, mock_setup, sample_application):
        """Exactly five LLM calls are made (1 summary + 4 sub-scores)."""
        responses = {
            "summary": '{"summary": "S", "postcode": "E1 1AA"}',
            "score_disturbance": '{"score_disturbance": 1}',
            "score_scale": '{"score_scale": 1}',
            "score_housing": '{"score_housing": 1}',
            "score_environment": '{"score_environment": 1}',
        }
        mock_client = self._make_mock_client(responses)
        mock_setup.return_value = mock_client

        pdf_data = [{"document_type": "Form", "text": "t"}]
        sample_application.analyse_pdf_text(pdf_data, "fake-key")

        assert mock_client.chat.completions.create.call_count == 5

    @patch.object(Application, '_setup_openai_client')
    def test_single_call_failure_raises(self, mock_setup, sample_application):
        """If one LLM call raises, the error propagates."""
        mock_client = MagicMock()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise ConnectionError("API timeout")
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = '{"summary": "S", "postcode": "E1 1AA"}'
            return mock_resp

        mock_client.chat.completions.create.side_effect = side_effect
        mock_setup.return_value = mock_client

        pdf_data = [{"document_type": "Form", "text": "t"}]
        with pytest.raises(ConnectionError):
            sample_application.analyse_pdf_text(pdf_data, "fake-key")

    @patch.object(Application, '_setup_openai_client')
    def test_missing_sub_score_raises_value_error(self, mock_setup, sample_application):
        """Raise ValueError if a sub-score call returns wrong key."""
        responses = {
            "summary": '{"summary": "S", "postcode": "E1 1AA"}',
            "score_disturbance": '{"score_disturbance": 1}',
            "score_scale": '{"score_scale": 1}',
            "score_housing": '{"wrong_key": 1}',
            "score_environment": '{"score_environment": 1}',
        }
        mock_setup.return_value = self._make_mock_client(responses)

        pdf_data = [{"document_type": "Form", "text": "t"}]
        with pytest.raises(ValueError, match="missing required fields"):
            sample_application.analyse_pdf_text(pdf_data, "fake-key")
