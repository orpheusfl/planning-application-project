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
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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
        # Create a session to handle cookies and retries
        session = requests.Session()

        # Configure retry strategy for resilience
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://development.towerhamlets.gov.uk/',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
            'Cookie'
        }

        # First request to establish session and get cookie
        session.get('https://development.towerhamlets.gov.uk/',
                    verify=False, headers=headers)

        # Now download the PDF with the session cookie
        response = session.get(
            url, verify=False, headers=headers, allow_redirects=True, timeout=30)
        response.raise_for_status()

        pdf_path = self._temp_dir / Path(url).name
        pdf_path.write_bytes(response.content)
        return pdf_path

    def store_pdf_data(self, pdfs: list[dict]) -> list[dict]:
        """Extract PDF files from URLs to temp storage with document type metadata.

        Args:
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys

        Returns:
            List of dicts with 'document_type' and 'pdf_data' (path) keys
        """
        stored_pdfs = []
        for pdf in pdfs:
            pdf_path = self.extract_pdf_from_url(pdf['pdf_url'])
            stored_pdfs.append({
                'document_type': pdf['document_type'],
                'pdf_data': pdf_path
            })
        return stored_pdfs

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


if __name__ == "__main__":
    sample_application = Application(
        application_number="PA/25/00973/A1",
        application_type="Full Planning Permission",
        description="Full planning application for the redevelopment of the site to provide non-residential floorspace/yard-space together with associated refuse stores, plant, secure cycle stores and car parking, and residential dwellings including affordable housing, together with the provision of landscaped public open space, refuse stores, plant, secure cycle stores and car parking for people with disabilities.",
        address="Iceland Wharf, Iceland Road, London E3 2JP",
        validation_date="Mon 09 Jun 2025",
        status="Registered",
        pdfs=[
            {"pdf_url": "https://development.towerhamlets.gov.uk/online-applications/files/0D7EF369DE41A10749E37876158B9790/pdf/PA_25_00973_A1-ADDENDUM-2294022.pdf",
             "document_type": "Planning Statement"},
            {"pdf_url": "https://development.towerhamlets.gov.uk/online-applications/files/6A4BC53103A5828430C02EA01F8277B2/pdf/PA_25_00973_A1-ADDENDUM___PART_1-2292216.pdf",
             "document_type": "Design & Access Statement"}
        ]
    )

    try:
        path_ = sample_application.extract_pdf_from_url(
            "https://development.towerhamlets.gov.uk/online-applications/pagedSearchResults.do?action=page&searchCriteria.page=1")
        print(f"PDF downloaded to: {path_}")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading PDF: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
