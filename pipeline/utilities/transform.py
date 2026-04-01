"""Utilities for transforming planning application data."""

import json
import logging
import os
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import fitz  # PyMuPDF
import openai
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from dotenv import load_dotenv

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options

from utilities.extract import extract_csrf_token
from utilities.config import LLM_MODEL, MAX_PARALLEL_LLM_CALLS, SUB_SCORE_RUBRICS


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()  # Load environment variables from .env file

POSTCODE_REGEX = r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b"


INCOMPLETE_POSTCODE_REGEX = r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\b"


class Application:
    """Represents a processed planning application with validated and enriched data."""

    def __init__(
        self,
        application_number: str,
        application_type: str,
        description: str,
        address: str,
        validation_date: str,
        status: str,
        pdfs: list[dict],
        decision: str,
        decision_date: str,
        database_action: str,
        urls: dict | None = None
    ) -> None:
        """Initialize with raw input data. Call process() to transform and enrich.

        Args:
            application_number: Unique identifier for the application
            application_type: Type of planning application
            description: Description of the planning application
            address: Full address including postcode
            validation_date: Date of validation as string (e.g., "Fri 20 Mar 2026")
            status: Current status of the application
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys
            urls: Optional dict with 'application_page_url' and 'document_page_url'
            decision: Decision string (e.g., "Approved", "Refused")
            decision_date: Decision date string (e.g., "Fri 20 Mar 2026")
            database_action: Database action string (e.g., "Insert", "Update")
        """
        if urls is None:
            urls = {}

        self.application_number = application_number
        self.application_type = application_type
        self.lat: float | None = None
        self.long: float | None = None
        self.validation_date: datetime | None = None
        self.status = status
        self.ai_summary: str | None = None
        self.application_page_url = urls.get('application_page_url')
        self.document_page_url = urls.get('document_page_url')
        self.public_interest_score: int | None = None
        self.score_scale: int | None = None
        self.score_disturbance: int | None = None
        self.score_environment: int | None = None
        self.score_housing: int | None = None
        self.decision = decision
        self.decision_date = decision_date
        self.database_action = database_action

        # Process and store address (no network calls)

        self.postcode = Application.extract_postcode_from_address(address)
        self.address = Application.format_address_by_removing_postcode(
            address, self.postcode)

        # Store raw inputs for processing
        self._raw_description = description
        self._raw_validation_date = validation_date
        self._raw_pdfs = pdfs

        # Create temporary directory for PDF storage
        self._temp_dir = Path(tempfile.mkdtemp())

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

    @staticmethod
    def extract_postcode_from_address(address: str) -> str:
        """Extract postcode from address string using regex. If only a partial postcode is found, return it for LLM validation later.

        Args:
            address: Full address string (e.g., "36A Grove Road, London, E3 5AX")

        Returns:
            Extracted postcode string (e.g., "E3 5AX") or empty string if not found
        """
        # Attempt to find a complete postcode first
        match = re.search(POSTCODE_REGEX, address)
        if match:
            return match.group(0)

        # If no complete postcode, look for an incomplete one (e.g., "E14", "W1A")
        match = re.search(INCOMPLETE_POSTCODE_REGEX, address)
        if match:
            incomplete_postcode = match.group(0)
            logger.info("Extracted incomplete postcode: %s",
                        incomplete_postcode)
            return incomplete_postcode

        logger.warning("No postcode found in address: %s", address)
        return ""

    @staticmethod
    def format_address_by_removing_postcode(address: str, postcode: str) -> str:
        """ Remove postcode from address string to create a 'clean' address field for database storage.

        Args:
            address: Full address string (e.g., "36A Grove Road, London, E3 5AX")
            postcode: Postcode string to remove from the address (e.g., "E3 5AX")

        Returns:
            Address string with postcode removed (e.g., "36A Grove Road, London")
        """

        address = address.strip()

        # Remove any postcode from the address for the 'address' field in the database
        formatted_address = re.sub(
            re.escape(postcode), '', address).strip(', ')

        return formatted_address

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

    def _build_summary_prompt(
            self,
            formatted_pdf_text: str,
            original_description: str,
            full_address: str,
            postcode_instructions: str) -> str:
        """Build a focused prompt that requests only the summary and postcode.

        Args:
            formatted_pdf_text: Pre-formatted PDF text block
            original_description: Original application description
            full_address: Complete address including postcode
            postcode_instructions: Instructions for postcode validation

        Returns:
            Prompt string requesting JSON with 'summary' and 'postcode' fields
        """
        return f"""Analyze this planning application and return a JSON response with two fields:

1. "summary": A 2-3 sentence summary highlighting key details residents need to
know (housing units, effects on neighboring property value, public amenities, traffic impact, transport links, affordable
housing percentage, environmental concerns). CRITICAL: Include inline references
directly within the summary text showing exactly which PDF section each fact came from.
Use the format: "...specific detail (<document_type>, page X)..." embedded
throughout the summary. For example: "The scheme includes 500 units of housing
(source: Application Form, page 2) with 25% affordable housing (source: Design Report, page 5)..."

2. "postcode": The complete and correct UK postcode for this application.
{postcode_instructions}

Respond ONLY with valid JSON, no additional text.

Original Application Description:
{original_description}

Full Address:
{full_address}

Extracted PDF Content:
{formatted_pdf_text}

Focus the summary on: proposed uses, number of units/buildings, key impacts on the
neighborhood, affordable housing provisions, and any notable amenities or concerns.
If there is no pdf content, summarise based on the original description.

Use UK English and be concise, but using full sentences. Avoid generic statements
and focus on specific details that would be relevant to local residents.

Return format:
{{"summary": "...", "postcode": "..."}}"""

    def _build_sub_score_prompt(
            self,
            score_name: str,
            formatted_pdf_text: str,
            original_description: str,
            full_address: str) -> str:
        """Build a focused prompt that requests a single sub-score.

        Args:
            score_name: Key into SUB_SCORE_RUBRICS (e.g. 'score_disturbance')
            formatted_pdf_text: Pre-formatted PDF text block
            original_description: Original application description
            full_address: Complete address including postcode

        Returns:
            Prompt string requesting JSON with one score field
        """
        rubric = SUB_SCORE_RUBRICS[score_name]

        return f"""Analyze this planning application and return a JSON response with one field:

{rubric}

Respond ONLY with valid JSON, no additional text.

Original Application Description:
{original_description}

Full Address:
{full_address}

Extracted PDF Content:
{formatted_pdf_text}

Return format:
{{"{score_name}": <1-5>}}"""

    def _call_llm(self, client: openai.OpenAI, system_message: str, prompt: str, label: str = "unknown") -> dict:
        """Make a single LLM API call and return the parsed JSON response.

        This is the isolated unit of work submitted to the thread pool.

        Args:
            client: Configured OpenAI client (thread-safe)
            system_message: System role content for the chat completion
            prompt: User role content for the chat completion
            label: Descriptive name for this call (used in log messages)

        Returns:
            Parsed JSON dict from the LLM response
        """
        start = time.perf_counter()

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
        )

        elapsed = time.perf_counter() - start
        logger.info("LLM call '%s' completed in %.2fs", label, elapsed)

        json_text = response.choices[0].message.content

        try:
            return json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            logger.error("Received response: %s", json_text)
            raise ValueError(f"Invalid JSON from LLM: {str(e)}") from e

    def _get_postcode_instructions(self, postcode: str) -> str:
        """Generate postcode validation instructions based on postcode completeness.

        Args:
            postcode: Postcode to check for completeness

        Returns:
            String with instructions for LLM postcode validation
        """
        if self._is_valid_postcode(postcode):
            return (
                f"The postcode '{postcode}' appears complete. Verify it matches "
                f"the address. Use this postcode if it is correct, otherwise find "
                f"the correct one from the PDF content."
            )

        return (
            f"The postcode '{postcode}' appears incomplete or invalid. Use the "
            f"PDF content and full address to find the complete, correct postcode. "
            f"If there is no postcode, try to find it based on the address and location details in the documents. "
            f"If you cannot find a valid postcode, find a postcode that is nearest to the location of the development based on the address and details in the documents."
        )

    def _is_valid_postcode(self, postcode: str) -> bool:
        """Check if postcode appears to be in valid UK format (complete).

        Valid UK postcodes are typically in format: A9A 9AA or A9 9AA or A99 9AA
        where A = letter, 9 = digit

        Args:
            postcode: Postcode string to validate

        Returns:
            True if postcode looks complete and valid, False otherwise
        """
        # Remove spaces for validation
        clean_postcode = postcode.replace(' ', '').upper()

        # Valid UK postcode pattern: 6-7 alphanumeric characters
        # Outward code (2-4 chars): letters and digits
        # Inward code (3 chars): digit followed by 2 letters
        # Simple check: if it's 6-7 chars with right pattern, likely valid
        if len(clean_postcode) < 6 or len(clean_postcode) > 7:
            return False

        # Check if inward code (last 3 chars) matches pattern: digit + 2 letters
        inward_code = clean_postcode[-3:]
        if not (inward_code[0].isdigit() and inward_code[1:].isalpha()):
            return False

        return True

    def _setup_openai_client(self, api_key: str) -> openai.OpenAI:
        """Set up OpenAI API client with the provided API key.

        Returns:
            Configured OpenAI client instance
        """
        try:
            client = openai.OpenAI(api_key=api_key)
            logger.info("OpenAI client initialized successfully")
            return client
        except Exception as e:
            logger.error(
                "Error initializing OpenAI client: %s", e, exc_info=True)
            raise

    def analyse_pdf_text(self, pdf_data: list[dict], api_key: str) -> dict:
        """Analyse application PDFs by dispatching parallel LLM calls.

        Sends five concurrent requests — one for the summary/postcode and one
        per sub-score — then merges the results into a single dict.

        Args:
            pdf_data: List of dicts with 'document_type' and 'text' keys
            api_key: OpenAI API key for authentication

        Returns:
            Dict with 'ai_summary', 'public_interest_score', 'score_*', and 'postcode' keys
        """
        client = self._setup_openai_client(api_key)
        system_message = (
            "You are a planning analyst that provides concise, "
            "resident-focused summaries. Always respond with valid JSON only."
        )

        formatted_pdf_text = "\n\n".join(
            f"{pdf['document_type'].upper()}:\n{pdf['text']}"
            for pdf in pdf_data
        )
        postcode_instructions = self._get_postcode_instructions(self.postcode)

        summary_prompt = self._build_summary_prompt(
            formatted_pdf_text,
            self._raw_description,
            self.address,
            postcode_instructions,
        )

        score_prompts = {
            score_name: self._build_sub_score_prompt(
                score_name,
                formatted_pdf_text,
                self._raw_description,
                self.address,
            )
            for score_name in SUB_SCORE_RUBRICS
        }

        total_start = time.perf_counter()

        # Dispatch all LLM calls in parallel and collect results
        merged = self._dispatch_parallel_llm_calls(
            client, system_message, summary_prompt, score_prompts,
        )

        total_elapsed = time.perf_counter() - total_start
        logger.info(
            "All %s parallel LLM calls completed in %.2fs",
            len(score_prompts) + 1, total_elapsed,
        )

        # Validate and assemble the final result
        return self._assemble_analysis_result(merged)

    def _dispatch_parallel_llm_calls(
        self,
        client: openai.OpenAI,
        system_message: str,
        summary_prompt: str,
        score_prompts: dict[str, str],
    ) -> dict:
        """Submit summary + sub-score prompts to the LLM in parallel and merge results.

        Each call returns a small JSON dict. The dicts are merged into one
        combined result containing the summary, postcode, and every sub-score.

        Args:
            client: Configured OpenAI client
            system_message: System-level instruction for the LLM
            summary_prompt: Prompt requesting the summary and postcode
            score_prompts: Mapping of score name → prompt for each sub-score

        Returns:
            Merged dict of all LLM response fields
        """
        merged: dict = {}
        futures: dict[str, object] = {}

        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_LLM_CALLS) as executor:
            # 1 summary/postcode call + 4 independent sub-score calls
            futures["summary"] = executor.submit(
                self._call_llm, client, system_message, summary_prompt, "summary",
            )
            for score_name, prompt in score_prompts.items():
                futures[score_name] = executor.submit(
                    self._call_llm, client, system_message, prompt, score_name,
                )

            # Collect results as each future completes
            for label, future in futures.items():
                result = future.result()
                merged.update(result)
                logger.info("Received result for '%s'", label)

        return merged

    def _assemble_analysis_result(self, merged: dict) -> dict:
        """Validate merged LLM results and compute the overall interest score.

        Args:
            merged: Combined dict from all parallel LLM calls

        Returns:
            Final analysis dict with ai_summary, public_interest_score,
            individual sub-scores, and postcode

        Raises:
            ValueError: If any required field is missing from the merged results
        """
        sub_score_names = list(SUB_SCORE_RUBRICS.keys())

        missing = [s for s in sub_score_names if s not in merged]
        if missing:
            raise ValueError(
                f"LLM responses missing required fields: {missing}")

        if "summary" not in merged:
            raise ValueError("LLM response missing required field: 'summary'")

        sub_scores = [merged[s] for s in sub_score_names]
        public_interest_score = round(sum(sub_scores) / len(sub_scores))

        return {
            'ai_summary': merged['summary'],
            'public_interest_score': public_interest_score,
            'score_disturbance': merged['score_disturbance'],
            'score_scale': merged['score_scale'],
            'score_housing': merged['score_housing'],
            'score_environment': merged['score_environment'],
            'postcode': merged.get('postcode', ''),
        }

    def _get_browser_cookies(self, url: str) -> tuple[list[dict], str | None]:
        """Retrieve cookies from browser after navigating to URL.

        Args:
            url: URL to navigate to in the browser

        Returns:
            Tuple of (cookies list, csrf_token string or None)
        """

        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

        driver = Chrome(options=options)

        try:
            driver.get(url)
            time.sleep(10)  # Wait longer for authentication to complete
            logger.info("Authenticated session established with browser")

            # Extract and log CSRF token for verification
            page_source = driver.page_source
            csrf_token = extract_csrf_token(page_source)
            if csrf_token:
                logger.info("CSRF token found: %s", csrf_token[:20] + "...")
            else:
                logger.warning("No CSRF token found in page")

            cookies = driver.get_cookies()
            logger.info("Retrieved %s cookies from Selenium", len(cookies))
            for cookie in cookies:
                cookie_value = cookie.get('value', '')
                value_display = (
                    str(cookie_value)[:20] + '...'
                    if len(str(cookie_value)) > 20
                    else cookie_value
                )
                logger.debug(
                    "Cookie: %s = %s (domain: %s)",
                    cookie.get('name'),
                    value_display,
                    cookie.get('domain')
                )
            return cookies, csrf_token
        finally:
            driver.quit()

    def _build_session_from_cookies(
            self,
            cookies: list[dict],
            csrf_token: str | None = None) -> requests.Session:
        """Create authenticated requests session with provided cookies.

        Args:
            cookies: List of cookie dictionaries to add to the session
            csrf_token: Optional CSRF token to include in session headers

        Returns:
            Configured requests.Session with cookies and headers
        """
        session = requests.Session()
        session.verify = False
        user_agent = (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 '
            'Safari/537.36'
        )
        session.headers.update({'User-Agent': user_agent})

        # Add CSRF token to headers if available
        if csrf_token:
            session.headers.update({
                'X-CSRF-Token': csrf_token,
                '_csrf': csrf_token
            })
            logger.debug("CSRF token added to session headers")

        for cookie in cookies:
            session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', ''),
                path=cookie.get('path', '/')
            )

        return session

    def _create_authenticated_session(self) -> requests.Session:
        """Create and return an authenticated requests session using Selenium.

        Returns:
            Authenticated requests.Session with cookies and CSRF token from browser
        """
        url = self.document_page_url or 'https://development.towerhamlets.gov.uk/'
        cookies, csrf_token = self._get_browser_cookies(url)
        return self._build_session_from_cookies(cookies, csrf_token)

    def _perform_pdf_download(self, session: requests.Session, url: str) -> Path:
        """Perform the actual PDF download and save to disk.

        Args:
            session: Authenticated requests.Session
            url: URL to the PDF file

        Returns:
            Path to the downloaded PDF file

        Raises:
            requests.exceptions.HTTPError: If HTTP error occurs
            requests.exceptions.RequestException: If request fails
        """
        response = session.get(url, stream=True, verify=False, timeout=10)
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

    def _download_pdf(self, session: requests.Session, url: str) -> Path | None:
        """Download PDF using an authenticated session with retry logic.

        Args:
            session: Authenticated requests.Session
            url: URL to the PDF file

        Returns:
            Path to the downloaded PDF file, or None if unavailable
        """
        logger.info("Downloading PDF from: %s", url)
        max_retries = 3
        base_delay = 1

        for attempt in range(max_retries):
            try:
                return self._perform_pdf_download(session, url)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    logger.warning("PDF not found (404): %s", url)
                    return None
                if e.response.status_code == 403:
                    logger.warning("PDF access forbidden (403): %s", url)
                    return None
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "HTTP error downloading PDF (attempt %s/%s): %s. Retrying in %s seconds...",
                        attempt + 1, max_retries, e, delay)
                    time.sleep(delay)
                else:
                    logger.error(
                        "HTTP error downloading PDF after %s attempts: %s", max_retries, e, exc_info=True)
                    raise
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        "Temporary network error downloading PDF (attempt %s/%s): %s. Retrying in %s seconds...",
                        attempt + 1, max_retries, e, delay)
                    time.sleep(delay)
                else:
                    logger.error(
                        "Network error downloading PDF after %s attempts: %s", max_retries, e, exc_info=True)
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(
                    "HTTP request error downloading PDF: %s", e, exc_info=True)
                raise
            except Exception as e:
                logger.error("Error downloading PDF: %s", e, exc_info=True)
                raise

    def pdf_urls_to_analysis(self, pdfs: list[dict], session: requests.Session, api_key: str) -> dict:
        """Complete pipeline: extract PDFs, extract text, clean, analyze, and return results.

        Downloads PDFs from provided URLs, extracts text from each, organizes by document type,
        builds a structured prompt, and analyzes with OpenAI LLM. Also stores PDF metadata
        and validates postcode using LLM.

        Args:
            pdfs: List of dicts with 'pdf_url' and 'document_type' keys
            session: Authenticated requests.Session for downloading PDFs
            api_key: OpenAI API key for authentication
        Returns:
            Dict with 'ai_summary' (str), 'public_interest_score' (int), 'postcode' (str), and 'pdfs' (list) keys
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

        logger.info("Analyzing with parallel LLM calls")
        analysis = self.analyse_pdf_text(pdf_texts, api_key)

        logger.info("PDF analysis completed successfully")
        return {
            'ai_summary': analysis['ai_summary'],
            'public_interest_score': analysis['public_interest_score'],
            'score_scale': analysis['score_scale'],
            'score_disturbance': analysis['score_disturbance'],
            'score_environment': analysis['score_environment'],
            'score_housing': analysis['score_housing'],
            'postcode': analysis['postcode']
        }

    def _cleanup_temp_files(self) -> None:
        """Remove temporary directory and all PDF files."""
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir)

    def _process_address(self) -> None:
        """Geocode postcode to get coordinates."""
        if self.postcode:
            coordinates = self.geocode_postcode(self.postcode)
            if coordinates:
                self.lat = coordinates[0]
                self.long = coordinates[1]
            else:
                logger.warning("Could not geocode postcode %s", self.postcode)

    def _process_validation_date(self) -> None:
        """Parse validation date string to datetime."""
        self.validation_date = self.parse_validation_date_to_datetime(
            self._raw_validation_date
        )

    def _process_pdfs(self, api_key: str) -> None:
        """Extract PDFs, analyze content, and store results."""
        # Create authenticated session once and reuse for analysis
        self._filter_pdfs_for_relevance()
        session = self._create_authenticated_session()

        try:
            pdf_analysis = self.pdf_urls_to_analysis(
                self._raw_pdfs, session, api_key)
            self.ai_summary = pdf_analysis['ai_summary']
            self.public_interest_score = pdf_analysis['public_interest_score']
            self.score_scale = pdf_analysis['score_scale']
            self.score_disturbance = pdf_analysis['score_disturbance']
            self.score_environment = pdf_analysis['score_environment']
            self.score_housing = pdf_analysis['score_housing']

            # Update postcode with LLM-validated version if provided
            postcode = pdf_analysis.get('postcode')
            if postcode:
                self.postcode = postcode
                logger.info("Postcode validated/updated to: %s", self.postcode)
        finally:
            session.close()

    def process(self, api_key: str) -> None:
        """Transform and enrich raw input data. Call this after __init__ to populate all fields."""

        logger.info(
            "Starting process pipeline for application %s - Application URL: %s | Document URL: %s",
            self.application_number, self.application_page_url, self.document_page_url)
        try:
            logger.info("Processing validation date...")
            self._process_validation_date()
            logger.info("Processing PDFs...")
            self._process_pdfs(api_key)
            logger.info(
                "Processing address (geocoding with validated postcode)...")
            self._process_address()
            logger.info("Process pipeline completed successfully")
        except Exception as e:
            logger.error("Error during process pipeline: %s", e, exc_info=True)
            raise
        finally:
            self._cleanup_temp_files()

    def _filter_pdfs_for_relevance(self):
        """Filter PDFs to include only those most relevant for resident-focused summary.
        Prints out the number of PDFs before and after filtering, and logs the percentage kept.
        Prints a list of the document types that were removed and kept after filtering for transparency."""

        relevant_types = {'application form',
                          'design and access statement',
                          'planning statement',
                          'consultation summary',
                          'environmental report'}

        initial_count = len(self._raw_pdfs)

        filtered_pdfs = [
            pdf for pdf in self._raw_pdfs if pdf['document_type'].lower() in relevant_types]
        final_count = len(filtered_pdfs)

        if initial_count > 0:
            percentage_kept = (final_count / initial_count) * 100
            logger.info(
                "Filtered PDFs for relevance: kept %s out of %s (%.2f%%)",
                final_count, initial_count, percentage_kept)
        else:
            logger.info("No PDFs to filter for relevance.")

        removed_types = {
            pdf['document_type']
            for pdf in self._raw_pdfs
            if pdf['document_type'].lower() not in relevant_types
        }
        kept_types = {
            pdf['document_type']
            for pdf in self._raw_pdfs
            if pdf['document_type'].lower() in relevant_types
        }

        if removed_types:
            logger.info("Removed PDF types: %s Kept PDF types: %s",
                        ", ".join(removed_types), ", ".join(kept_types))

        self._raw_pdfs = filtered_pdfs

    def to_dict(self) -> dict:
        """Convert application data to dictionary ready for database insertion.

        Ensure process() has been called before using this method.

        Returns:
            Dict with all application fields ready for RDS loading
        """
        decided_at = None
        if self.decision_date:
            decided_at = self.parse_validation_date_to_datetime(
                self.decision_date)

        return {
            'application_number': self.application_number,
            'application_type': self.application_type,
            'address': self.address,
            'postcode': self.postcode,
            'lat': self.lat,
            'long': self.long,
            'validation_date': self.validation_date,
            'status_type': self.status,
            'ai_summary': self.ai_summary,
            'public_interest_score': self.public_interest_score,
            'score_scale': self.score_scale,
            'score_disturbance': self.score_disturbance,
            'score_environment': self.score_environment,
            'score_housing': self.score_housing,
            'application_page_url': self.application_page_url,
            'document_page_url': self.document_page_url,
            'decision_type': self.decision,
            'decided_at': decided_at,
            'database_action': self.database_action
        }


if __name__ == "__main__":
    # full example usage with incorrect postcode to demonstrate LLM validation
    example_application = Application(
        application_number="PA/26/00490/S",
        application_type="Approval of Details -Discharge Condition",
        description=(
            "Submission of details pursuant to condition no.49 "
            "(Post Completion Verification Report), for phase 1 block B, of hybrid "
            "planning permission ref: PA/18/02803, dated 30/10/2019"
        ),
        address="Poplar Gas Holder Site, Leven Road, London, E14",
        validation_date="Wed 18 Mar 2026",
        status="Registered",
        pdfs=[
            {
                'pdf_url': (
                    'https://development.towerhamlets.gov.uk/'
                    'online-applications/files/E3D00DF035754FBBF1AC126F1924C392/pdf/'
                    'PA_26_00490_S--2339689.pdf'
                ),
                'document_type': 'Application Form'
            },
            {
                'pdf_url': (
                    'https://development.towerhamlets.gov.uk/'
                    'online-applications/files/23718CD4D01E07522B2E034FC07B345C/pdf/'
                    'PA_26_00490_S-COVERING_LETTER_DATED__25_FEB_2026-2339867.pdf'
                ),
                'document_type': 'Correspondence'
            }
        ],
        urls={
            'application_page_url': (
                'https://development.towerhamlets.gov.uk/'
                'online-applications/applicationDetails.do'
                '?activeTab=summary&keyVal=DCAPR_150275'
            ),
            'document_page_url': (
                'https://development.towerhamlets.gov.uk/'
                'online-applications/applicationDetails.do'
                '?activeTab=documents&keyVal=DCAPR_150275'
            )
        }
    )

    example_application.process(api_key=os.getenv("OPENAI_API_KEY"))
    application_data = example_application.to_dict()
    print(json.dumps(application_data, indent=2, default=str))
