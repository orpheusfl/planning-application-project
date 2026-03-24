"""Utilities for transforming planning application data.
    This module will take in:
    
    {application_number:
    address:
    validation_date:
    description:
    status:
    application_type:
    pdfs: list[{pdf_url: str, document_type: str}]}
    
    And will output a dictionary ready to be loaded into RDS with the following structure:
    {
    application_number: str
    application_type: str
    address: str
    postcode: str
    lat: float
    long: float
    validation_date: datetime
    status: str
    ai_summary: str
    public_interest_score: int
    pdfs: list[dict{document_type: str, pdf_data: bytes}]
    }
    """

import shutil
import tempfile
from datetime import datetime
from pathlib import Path


class Application:
    """Represents a processed planning application with validated and enriched data."""

    def __init__(self,
                 application_number: str,
                 application_type: str,
                 description: str,
                 address: str,
                 validation_date: str,
                 status: str,
                 pdfs: list[dict]) -> None:
        """Initialize with raw input data. Call process() to transform and enrich.

        Args:
            application_number: Unique identifier for the application
            application_type: Type of planning application
            description: Description of the planning application
            address: Full address including postcode
            validation_date: Date of validation as string (e.g., "Fri 20 Mar 2026")
            status: Current status of the application
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys
        """
        self.application_number = application_number
        self.application_type = application_type
        self.address: str | None = None
        self.postcode: str | None = None
        self.lat: float | None = None
        self.long: float | None = None
        self.validation_date: datetime | None = None
        self.status = status
        self.ai_summary: str | None = None
        self.public_interest_score: int | None = None
        self.pdfs: list[dict] | None = None

        # Store raw inputs for processing
        self._raw_address = address
        self._raw_description = description
        self._raw_validation_date = validation_date
        self._raw_pdfs = pdfs

        # Create temporary directory for PDF storage
        self._temp_dir = Path(tempfile.mkdtemp())

    def process(self) -> None:
        """Transform and enrich raw input data. Call this after __init__ to populate all fields."""
        try:
            self._process_address()
            self._process_validation_date()
            self._process_pdfs()
        finally:
            self._cleanup_temp_files()

    def _cleanup_temp_files(self) -> None:
        """Remove temporary directory and all PDF files."""
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)

    def _process_address(self) -> None:
        """Extract postcode and coordinates from address."""
        address_data = self.get_postcode_and_address_from_address(
            self._raw_address)
        self.address = address_data['address']
        self.postcode = address_data['postcode']

        coordinates = self.get_lat_and_long_from_address(self._raw_address)
        self.lat = coordinates['lat']
        self.long = coordinates['long']

    def _process_validation_date(self) -> None:
        """Parse validation date string to datetime."""
        self.validation_date = self.parse_validation_date_to_datetime(
            self._raw_validation_date
        )

    def _process_pdfs(self) -> None:
        """Extract PDFs, analyze content, and store results."""
        pdf_analysis = self.pdf_urls_to_analysis(self._raw_pdfs)
        self.ai_summary = pdf_analysis['ai_summary']
        self.public_interest_score = pdf_analysis['public_interest_score']
        self.pdfs = self.store_pdf_data(self._raw_pdfs)

    def extract_pdf_from_url(self, url: str) -> Path:
        """Download and extract PDF file from URL to temporary storage.

        Args:
            url: URL to the PDF file

        Returns:
            Path to the downloaded PDF file in temp directory
        """
        pass

    def store_pdf_data(self, pdfs: list[dict]) -> list[dict]:
        """Extract PDF files from URLs to temp storage with document type metadata.

        Args:
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys

        Returns:
            List of dicts with 'document_type' and 'pdf_data' (bytes) keys
        """
        pass

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract main body text from PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        pass

    def clean_pdf_text(self, text: str) -> str:
        """Remove irrelevant information from extracted PDF text.

        Args:
            text: Raw text extracted from PDF

        Returns:
            Cleaned text ready for analysis
        """
        pass

    def build_llm_analysis_prompt(self, pdf_text: list[str], original_description: str) -> str:
        """Build structured prompt for LLM analysis combining PDF text and description.

        Args:
            pdf_text: List of extracted and cleaned text from PDFs
            original_description: Original application description

        Returns:
            Prompt string for LLM analysis
        """
        pass

    def analyse_pdf_text(self, prompt: str) -> dict:
        """Analyze prompt using LLM API and return structured output.

        Args:
            prompt: Prompt string for LLM analysis

        Returns:
            Dict with 'ai_summary' (str) and 'public_interest_score' (int) keys
        """
        pass

    def pdf_urls_to_analysis(self, pdfs: list[dict]) -> dict:
        """Complete pipeline: extract PDFs, extract text, clean, analyze, and return results.

        Args:
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys

        Returns:
            Dict with 'ai_summary' (str) and 'public_interest_score' (int) keys
        """
        pass

    def get_postcode_and_address_from_address(self, address: str) -> dict:
        """Extract postcode and address components.

        Removes postcode from full address and formats both components.

        Args:
            address: Full address string (e.g., "36A Grove Road, London, E3 5AX")

        Returns:
            Dict with 'address' and 'postcode' keys
            Example: {'address': '36A Grove Road, London', 'postcode': 'E35AX'}
        """
        pass

    def get_lat_and_long_from_address(self, address: str) -> dict:
        """Get geographic coordinates for address using geocoding API.

        Args:
            address: Full address string

        Returns:
            Dict with 'lat' (float) and 'long' (float) keys
        """
        pass

    def parse_validation_date_to_datetime(self, validation_date: str) -> datetime:
        """Parse validation date string to datetime object.

        Args:
            validation_date: Date string (e.g., "Fri 20 Mar 2026")

        Returns:
            Parsed datetime object
        """
        pass

    def to_dict(self) -> dict:
        """Convert application data to dictionary ready for database insertion.

        Ensure process() has been called before using this method.

        Returns:
            Dict with all application fields ready for RDS loading
        """
        return {
            'application_number': self.application_number,
            'application_type': self.application_type,
            'address': self.address,
            'postcode': self.postcode,
            'lat': self.lat,
            'long': self.long,
            'validation_date': self.validation_date,
            'status': self.status,
            'ai_summary': self.ai_summary,
            'public_interest_score': self.public_interest_score,
            'pdfs': self.pdfs
        }
