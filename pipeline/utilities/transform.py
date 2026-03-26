"""Utilities for transforming planning application data."""

import json
import logging
import os
import re
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
import openai
import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv
from selenium import webdriver


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()  # Load environment variables from .env file

API_KEY = os.getenv("OPENAI_API_KEY")

POSTCODE_REGEX = r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b"


class Application:
    """Represents a processed planning application with validated and enriched data."""

    def __init__(self,
                 application_number: str,
                 application_type: str,
                 description: str,
                 address: str,
                 validation_date: str,
                 status: str,
                 pdfs: list[dict],
                 application_url: str | None = None,
                 document_page_url: str | None = None) -> None:
        """Initialize with raw input data. Call process() to transform and enrich.

        Args:
            application_number: Unique identifier for the application
            application_type: Type of planning application
            description: Description of the planning application
            address: Full address including postcode
            validation_date: Date of validation as string (e.g., "Fri 20 Mar 2026")
            status: Current status of the application
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys
            application_url: Optional URL to the application details page for 
            establishing session context
            document_page_url: Optional URL to the document page for the application
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
        self.application_url = application_url
        self.document_page_url = document_page_url
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
        logger.info(
            "Starting process pipeline for application %s", self.application_number)
        try:
            logger.info("Processing address...")
            self._process_address()
            logger.info("Processing validation date...")
            self._process_validation_date()
            logger.info("Processing PDFs...")
            self._process_pdfs()
            logger.info("Process pipeline completed successfully")
        except Exception as e:
            logger.error("Error during process pipeline: %s", e, exc_info=True)
            raise
        finally:
            self._cleanup_temp_files()

    def _cleanup_temp_files(self) -> None:
        """Remove temporary directory and all PDF files."""
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)

    def _process_address(self) -> None:
        """Extract postcode and coordinates from address."""
        address_data = self.format_address(self._raw_address)
        self.address = address_data['address']
        self.postcode = address_data['postcode']

        if self.postcode:
            coordinates = self.geocode_postcode(self.postcode)
            if coordinates:
                self.lat = coordinates[0]
                self.long = coordinates[1]
            else:
                logger.warning("Could not geocode postcode %s", self.postcode)
                self.lat = None
                self.long = None

    def _process_validation_date(self) -> None:
        """Parse validation date string to datetime."""
        self.validation_date = self.parse_validation_date_to_datetime(
            self._raw_validation_date
        )

    def _process_pdfs(self) -> None:
        """Extract PDFs, analyze content, and store results."""
        # Create authenticated session once and reuse for both analysis and storage
        session = self._create_authenticated_session()

        try:
            pdf_analysis = self.pdf_urls_to_analysis(self._raw_pdfs, session)
            self.ai_summary = pdf_analysis['ai_summary']
            self.public_interest_score = pdf_analysis['public_interest_score']

            # Store PDFs using the same authenticated session (no second download)
            self.pdfs = self._extract_downloaded_pdfs(self._raw_pdfs, session)
        finally:
            session.close()

    def _create_authenticated_session(self) -> requests.Session:
        """Create and return an authenticated requests session using Selenium.

        Returns:
            Authenticated requests.Session with cookies from browser
        """
        driver = webdriver.Chrome()
        try:
            # Navigate to application page to authenticate
            url = self.document_page_url or 'https://development.towerhamlets.gov.uk/'
            driver.get(url)
            time.sleep(5)  # Wait for cookies to be set
            logger.info("Authenticated session established with browser")

            # Extract cookies from the active session
            cookies = driver.get_cookies()
            logger.info("Retrieved %s cookies from Selenium", len(cookies))

            # Create a requests session with the active cookies
            session = requests.Session()
            session.verify = False
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })

            # Add cookies to the session while the Selenium session is still active
            for cookie in cookies:
                session.cookies.set(
                    cookie['name'],
                    cookie['value'],
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/')
                )

            return session
        finally:
            driver.quit()

    def _extract_downloaded_pdfs(self, pdfs: list[dict], session: requests.Session) -> list[dict]:
        """Convert downloaded PDF paths to storage format.

        Assumes PDFs have already been downloaded and are in temp storage.
        Returns metadata with paths ready for storage.

        Args:
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys
            session: Authenticated session (used to download PDFs if needed)

        Returns:
            List of dicts with 'document_type' and 'pdf_data' (path) keys
        """
        logger.info("Starting PDF extraction for %s PDFs", len(pdfs))
        stored_pdfs = []

        for idx, pdf in enumerate(pdfs, 1):
            logger.info(
                "Processing PDF %s/%s: %s", idx, len(pdfs), pdf['document_type'])
            try:
                pdf_path = self._download_pdf(session, pdf['pdf_url'])
                if pdf_path is None:
                    logger.info(
                        "Skipping %s - PDF not available", pdf['document_type'])
                    continue

                stored_pdfs.append({
                    'document_type': pdf['document_type'],
                    'pdf_data': pdf_path
                })
            except Exception as e:
                logger.error(
                    "Failed to extract PDF %s: %s", idx, e, exc_info=True)
                raise

        logger.info("All %s PDFs extracted successfully", len(stored_pdfs))
        return stored_pdfs

    def _download_pdf(self, session: requests.Session, url: str) -> Path | None:
        """Download PDF using an authenticated session.

        Args:
            session: Authenticated requests.Session
            url: URL to the PDF file

        Returns:
            Path to the downloaded PDF file, or None if unavailable
        """
        logger.info("Downloading PDF from: %s", url)
        try:
            response = session.get(url, stream=True, verify=False)
            response.raise_for_status()

            pdf_filename = url.split('/')[-1]
            pdf_path = self._temp_dir / pdf_filename

            bytes_downloaded = 0
            with open(pdf_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)

            logger.info(
                "PDF downloaded successfully (%s bytes) to %s", bytes_downloaded, pdf_path)
            return pdf_path
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning("PDF not found (404): %s", url)
                return None
            logger.error("HTTP error downloading PDF: %s", e, exc_info=True)
            raise
        except requests.exceptions.RequestException as e:
            logger.error(
                "HTTP request error downloading PDF: %s", e, exc_info=True)
            raise
        except Exception as e:
            logger.error("Error downloading PDF: %s", e, exc_info=True)
            raise

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract main body text from PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted text content with page numbers for reference (e.g., "Page 1: ... Page 2: ...")
        """

        try:
            doc = fitz.open(pdf_path)
            text = ""
            for page_number, page in enumerate(doc, start=1):
                text += f"Page {page_number}:\n{page.get_text()}\n"
            return text
        except Exception as e:
            logger.error("Error extracting text from PDF: %s",
                         e, exc_info=True)
            raise

    def clean_pdf_text(self, text: str) -> str:
        """Remove irrelevant information from extracted PDF text.

        Args:
            text: Raw text extracted from PDF

        Returns:
            Cleaned text ready for analysis
        """
        text = text.strip()
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        text = '\n'.join(cleaned_lines)
        text = ' '.join(text.split())
        return text

    def build_llm_analysis_prompt(self, pdf_data: list[dict], original_description: str) -> str:
        """Build structured prompt for LLM analysis combining PDF text and description.

        Args:
            pdf_data: List of dicts with 'document_type' and 'text' keys from extracted PDFs
            original_description: Original application description

        Returns:
            Prompt string for LLM analysis requesting JSON output
        """
        formatted_pdf_text = "\n\n".join(
            f"{pdf['document_type'].upper()}:\n{pdf['text']}"
            for pdf in pdf_data
        )

        prompt = f"""Analyze this planning application and return a JSON response with two fields:
                    1. "summary": A 2-3 sentence summary highlighting key details residents need to 
                    know (housing units, density, public amenities, traffic impact, affordable 
                    housing percentage, environmental concerns). Do inline referencing to the exact PDF document
                    sections where you found key information (e.g., "According to the Decision Notice, page 3...").
                    2. "public_interest_score": An integer from 1-10 assessing public interest level

                    Respond ONLY with valid JSON, no additional text.

                    Original Application Description:
                    {original_description}

                    Extracted PDF Content:
                    {formatted_pdf_text}

                    Focus the summary on: proposed uses, number of units/buildings, 
                    key impacts on the neighborhood, affordable housing provisions, 
                    and any notable amenities or concerns. If there is no pdf content, 
                    summarise based on the original description.

                    Use UK English and be concise, but using full sentences. Avoid generic statements 
                    and focus on specific details that would be relevant to local residents.

                    Return format:
                    {{"summary": "...", "public_interest_score": <number>}}"""
        return prompt

    def _setup_openai_client(self) -> openai.OpenAI:
        """Set up OpenAI API client with the provided API key.

        Returns:
            Configured OpenAI client instance
        """
        try:
            client = openai.OpenAI(api_key=API_KEY)
            logger.info("OpenAI client initialized successfully")
            return client
        except Exception as e:
            logger.error(
                "Error initializing OpenAI client: %s", e, exc_info=True)
            raise

    def analyse_pdf_text(self, prompt: str) -> dict:
        """Analyze prompt using OpenAI LLM API and return structured output.

        Args:
            prompt: Prompt string for LLM analysis

        Returns:
            Dict with 'ai_summary' (str) and 'public_interest_score' (int) keys
        """
        client = self._setup_openai_client()

        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": "You are a planning analyst that provides concise, resident-focused summaries. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ]
        )

        logger.info("Received response from OpenAI API")

        json_text = response.choices[0].message.content
        result = json.loads(json_text)

        return {
            'ai_summary': result['summary'],
            'public_interest_score': result['public_interest_score']
        }

    def pdf_urls_to_analysis(self, pdfs: list[dict], session: requests.Session) -> dict:
        """Complete pipeline: extract PDFs, extract text, clean, analyze, and return results.

        Downloads PDFs from provided URLs, extracts text from each, organizes by document type,
        builds a structured prompt, and analyzes with OpenAI LLM.

        Args:
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys
            session: Authenticated requests.Session for downloading PDFs

        Returns:
            Dict with 'ai_summary' (str) and 'public_interest_score' (int) keys
        """
        logger.info("Starting PDF analysis pipeline for %s PDFs", len(pdfs))

        pdf_texts = []

        for idx, pdf in enumerate(pdfs, 1):
            logger.info(
                "Processing PDF %s/%s: %s", idx, len(pdfs), pdf['document_type'])
            try:
                pdf_path = self._download_pdf(session, pdf['pdf_url'])
                if pdf_path is None:
                    logger.info(
                        "Skipping %s - PDF not available", pdf['document_type'])
                    continue

                raw_text = self.extract_text_from_pdf(pdf_path)
                cleaned_text = self.clean_pdf_text(raw_text)

                pdf_texts.append({
                    'document_type': pdf['document_type'],
                    'text': cleaned_text
                })
                logger.info(
                    "Successfully processed %s", pdf['document_type'])

            except Exception as e:
                logger.error(
                    "Failed to process PDF %s (%s): %s", idx, pdf['document_type'], e,
                    exc_info=True
                )
                raise

        logger.info("Building LLM analysis prompt")
        prompt = self.build_llm_analysis_prompt(
            pdf_texts, self._raw_description)

        logger.info("Analyzing with OpenAI LLM")
        analysis = self.analyse_pdf_text(prompt)

        logger.info("PDF analysis completed successfully")
        return analysis

    def format_address(self, address: str) -> dict:
        """Extract unique elements from the address string.

        Args:
            address: Full address string (e.g., "36A Grove Road, London, E3 5AX")

        Returns:
            Dict with 'street' (str), 'city' (str), 'postalcode' (str), and 'country' (str) keys
            Example: {'street': '36A Grove Road', 'city': 'London', 'postalcode': 'E35AX', 'country': 'UK'}
        """

        address = address.strip()
        postcode_match = re.search(POSTCODE_REGEX, address)
        if not postcode_match:
            logger.warning("No postcode found in address: %s", address)
            raise ValueError(
                f"Could not extract postcode from address: {address}")

        postcode = postcode_match.group(0)
        address_without_postcode = address.replace(
            postcode, "").strip(", ").strip()

        return {'address': address_without_postcode, 'postcode': postcode}

    def geocode_postcode(self, postcode: str) -> tuple[float, float] | None:
        """Convert a UK postcode to (lat, lon) via postcodes.io.

        Results are cached for one hour to avoid repeated API calls.
        Returns ``None`` when the postcode cannot be resolved.
        """
        try:
            resp = requests.get(
                f"https://api.postcodes.io/postcodes/{postcode.strip()}",
                timeout=5,
            )
            data = resp.json()
            if data["status"] == 200:
                return data["result"]["latitude"], data["result"]["longitude"]
        except requests.RequestException:
            pass
        return None

    def parse_validation_date_to_datetime(self, validation_date: str) -> datetime:
        """Parse validation date string to datetime object.
        ensure this can handle various date formats and log any parsing issues for debugging.

        Args:
            validation_date: Date string (e.g., "Fri 20 Mar 2026")

        Returns:
            Parsed datetime object
        """

        try:
            parsed_date = date_parser.parse(
                validation_date, fuzzy=True, dayfirst=True)
            return parsed_date
        except (ValueError, OverflowError) as e:
            logger.error(
                "Error parsing validation date '%s': %s", validation_date, e, exc_info=True)
            raise

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
