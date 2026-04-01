"""
Module for downloading planning application PDFs and extracting their text
content for use in the RAG model.

This module is self-contained and does not import from any other project modules.
It connects to the RDS database to look up an application's document page URL,
scrapes the Idox planning portal for PDF links, downloads each PDF, and extracts
the text content ready for RAG indexing.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import fitz  # PyMuPDF
import psycopg2
import urllib3
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup

from dotenv import load_dotenv


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"


# -----------------------------------------------------
# Session Management and State Priming
# -----------------------------------------------------


def create_scraper_session() -> requests.Session:
    """Initialises a persistent session with standard browser headers and disabled SSL."""
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) "
            "Gecko/20100101 Firefox/148.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    })
    return session


def acquire_session_cookie(session: requests.Session, url: str) -> bool:
    """Hits the homepage to establish the initial JSESSIONID cookie."""
    logger.info("Acquiring fresh JSESSIONID...")

    try:
        session.get(url, timeout=10)
    except RequestException as e:
        logger.error("Network error acquiring cookie: %s", e)
        return False

    if "JSESSIONID" not in session.cookies:
        logger.error("Failed to capture JSESSIONID")
        return False

    cookie_preview = session.cookies["JSESSIONID"][:10]
    logger.info("Success: Captured JSESSIONID (%s...)", cookie_preview)
    return True


def extract_csrf_token(html_content: str) -> Optional[str]:
    """Parses HTML to find the hidden CSRF security token required for POST requests."""
    soup = BeautifulSoup(html_content, "html.parser")
    csrf_input = soup.find("input", {"name": "_csrf"})

    if csrf_input and isinstance(csrf_input.get("value"), str):
        return csrf_input.get("value")
    return None


def _check_for_server_error(html_content: str) -> bool:
    """Returns True if the server responded with a session timeout or error page."""
    if "session has timed out" in html_content.lower():
        return True

    soup = BeautifulSoup(html_content, "html.parser")
    if soup.title and "error" in soup.title.string.lower():
        return True

    return False


def prime_session_state(session: requests.Session, url: str) -> bool:
    """
    Navigates the Idox system to establish the server-side search state.
    Requires handling a CSRF token and mimicking a specific form submission.
    """
    logger.info("Priming server state (Handling CSRF & POST)...")
    search_page_url = f"{url}search.do?action=advanced"

    try:
        get_response = session.get(search_page_url, timeout=10)
        csrf_token = extract_csrf_token(get_response.text)

        if not csrf_token:
            logger.error("Could not find the _csrf token in the page HTML")
            return False

        logger.debug("Found CSRF Token: %s", csrf_token)

        primer_url = f"{url}currentListResults.do?action=firstPage"
        payload = {
            "_csrf": csrf_token,
            "currentListSearch": "true",
            "searchCriteria.currentListSearch": "true",
            "searchType": "Application",
        }

        session.headers.update({"Referer": search_page_url})
        post_response = session.post(primer_url, data=payload, timeout=10)

        if _check_for_server_error(post_response.text):
            logger.error("Server returned an error or timeout during priming")
            return False

        logger.info("Server state primed successfully")
        return True
    except RequestException as e:
        logger.error("Network error during session priming: %s", e)
        return False


def initialise_session() -> requests.Session | None:
    """Creates a scraper session, acquires cookies, and primes the Idox server state.

    Returns:
        A fully initialised requests session, or None if initialisation failed.
    """
    session = create_scraper_session()

    if not acquire_session_cookie(session, BASE_URL):
        logger.error("Failed to acquire session cookie")
        return None

    if not prime_session_state(session, BASE_URL):
        logger.error("Failed to prime session state")
        return None

    return session


# -----------------------------------------------------
# URL Construction Helpers
# -----------------------------------------------------


def build_documents_tab_url(application_page_url: str) -> str:
    """Converts an application page URL to point at the documents tab.

    Swaps the 'activeTab' query parameter to 'documents' in an Idox application URL.

    Args:
        application_page_url: URL for any tab of the application (e.g. summary).

    Returns:
        The URL pointing to the documents tab.
    """
    parsed = urlparse(application_page_url)
    params = parse_qs(parsed.query)
    params["activeTab"] = ["documents"]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


# -----------------------------------------------------
# RDS Database Queries
# -----------------------------------------------------


def get_rds_connection(rds_host: str, rds_port: int, rds_user: str,
                       rds_password: str, rds_db_name: str):
    """Establish a connection to the RDS database.

    Args:
        rds_host: Database hostname.
        rds_port: Database port number.
        rds_user: Database username.
        rds_password: Database password.
        rds_db_name: Name of the database.

    Returns:
        An active psycopg2 connection object.
    """
    conn = psycopg2.connect(
        host=rds_host,
        port=rds_port,
        user=rds_user,
        password=rds_password,
        dbname=rds_db_name,
    )
    logger.info("Successfully connected to RDS database.")
    return conn


def get_document_page_url(conn, application_number: str) -> str | None:
    """Query the RDS database for the document page URL of a planning application.

    Falls back to deriving the documents URL from the application page URL
    if no document_page_url is stored directly.

    Args:
        conn: Active psycopg2 database connection.
        application_number: Unique reference number (e.g. 'PA/26/00515/NC').

    Returns:
        The document page URL string, or None if the application was not found.
    """
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT document_page_url, application_page_url
            FROM application
            WHERE application_number = %s
        """, (application_number,))
        result = cursor.fetchone()

    if not result:
        logger.warning("Application not found in database: %s",
                       application_number)
        return None

    document_url, application_url = result

    if document_url:
        return document_url

    if application_url:
        logger.info("Deriving documents URL from application page URL")
        return build_documents_tab_url(application_url)

    logger.warning("No URLs found for application: %s", application_number)
    return None


# -----------------------------------------------------
# Network Fetching
# -----------------------------------------------------


def fetch_page(session: requests.Session, url: str) -> str | None:
    """Fetches a page using the session and returns its HTML content.

    Args:
        session: Active requests session with cookies set.
        url: URL to fetch.

    Returns:
        HTML content string, or None if the request failed.
    """
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except RequestException as e:
        logger.error("Request failed for URL %s: %s", url, e)
        return None


# -----------------------------------------------------
# Document Page Parsing
# -----------------------------------------------------


def parse_pdf_links_from_html(html_content: str, page_url: str) -> list[dict[str, str]]:
    """Parses the Documents tab HTML to extract PDF URLs and their document types.

    The Idox documents table has a standard column layout where index 2 holds the
    document type and index 5 contains the download link.

    Args:
        html_content: Raw HTML string of the documents page.
        page_url: URL of the documents page, used for resolving relative links.

    Returns:
        A list of dicts, each with 'pdf_url' and 'document_type' keys.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    documents_table = soup.find("table", id="Documents")

    if not documents_table:
        logger.warning("No documents table found on page: %s", page_url)
        return []

    pdf_documents: list[dict[str, str]] = []

    for row in documents_table.find_all("tr"):
        cols = row.find_all("td")

        if len(cols) < 6:
            continue

        document_type = cols[2].get_text(strip=True)
        view_link_tag = cols[5].find("a", href=True)

        if not view_link_tag:
            continue

        pdf_url = urljoin(page_url, view_link_tag["href"])
        pdf_documents.append({
            "pdf_url": pdf_url,
            "document_type": document_type,
        })

    logger.info("Found %d PDF documents on page", len(pdf_documents))
    return pdf_documents


def get_pdf_links_from_page(session: requests.Session, url: str) -> list[dict[str, str]]:
    """Fetches an application's documents page and extracts all PDF links.

    Args:
        session: Initialised requests session with cookies set.
        url: URL of the documents tab for the application.

    Returns:
        A list of dicts with 'pdf_url' and 'document_type' keys. Empty list on failure.
    """
    html_content = fetch_page(session, url)

    if not html_content:
        logger.error("Failed to fetch documents page: %s", url)
        return []

    if _check_for_server_error(html_content):
        logger.error("Server error on documents page: %s", url)
        return []

    return parse_pdf_links_from_html(html_content, url)


# -----------------------------------------------------
# PDF Download and Text Extraction
# -----------------------------------------------------


def download_pdf(session: requests.Session, url: str, download_dir: Path) -> Path | None:
    """Downloads a PDF from the given URL and saves it to the specified directory.

    Args:
        session: Active requests session with cookies set.
        url: Direct URL to the PDF file.
        download_dir: Directory path to save the downloaded PDF.

    Returns:
        Path to the downloaded file, or None if the PDF was unavailable (404/403).
    """
    logger.info("Downloading PDF from: %s", url)

    try:
        response = session.get(url, stream=True, verify=False, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else None
        if status_code in (403, 404):
            logger.warning("PDF unavailable (HTTP %s): %s", status_code, url)
            return None
        raise
    except RequestException as e:
        logger.error("Network error downloading PDF from %s: %s", url, e)
        raise

    pdf_filename = url.split("/")[-1]
    pdf_path = download_dir / pdf_filename

    bytes_downloaded = 0
    with open(pdf_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            bytes_downloaded += len(chunk)

    logger.info("Downloaded %d bytes to %s", bytes_downloaded, pdf_path)
    return pdf_path


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extracts text content from a PDF file using PyMuPDF.

    Each page's text is prefixed with a page number for reference traceability
    in downstream RAG citations.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        Extracted text with page number annotations.
    """
    doc = fitz.open(pdf_path)
    pages: list[str] = []

    for page_number, page in enumerate(doc, start=1):
        pages.append(f"Page {page_number}:\n{page.get_text()}")

    doc.close()
    return "\n".join(pages)


def clean_pdf_text(text: str) -> str:
    """Removes excess whitespace, blank lines, and non-breaking spaces from PDF text.

    Args:
        text: Raw text extracted from a PDF.

    Returns:
        Cleaned text string with normalised whitespace.
    """
    text = text.strip()
    lines = text.split("\n")
    cleaned_lines = [line.strip() for line in lines if line.strip()]
    return " ".join(" ".join(cleaned_lines).split())


# -----------------------------------------------------
# Orchestration
# -----------------------------------------------------


def extract_document_texts(
    session: requests.Session,
    pdf_links: list[dict[str, str]],
    download_dir: Path,
) -> list[dict[str, str]]:
    """Downloads each PDF and extracts cleaned text content.

    Args:
        session: Initialised requests session with cookies set.
        pdf_links: List of dicts with 'pdf_url' and 'document_type' keys.
        download_dir: Temporary directory for storing downloaded PDFs.

    Returns:
        A list of dicts with 'document_type' and 'document_text' keys.
    """
    documents: list[dict[str, str]] = []

    for idx, pdf_info in enumerate(pdf_links, start=1):
        pdf_url = pdf_info["pdf_url"]
        document_type = pdf_info["document_type"]
        logger.info("Processing PDF %d/%d: %s", idx,
                    len(pdf_links), document_type)

        pdf_path = download_pdf(session, pdf_url, download_dir)
        if pdf_path is None:
            logger.info("Skipping unavailable PDF: %s", document_type)
            continue

        raw_text = extract_text_from_pdf(pdf_path)
        cleaned_text = clean_pdf_text(raw_text)

        documents.append({
            "document_type": document_type,
            "document_text": cleaned_text,
        })

        logger.info("Extracted text from: %s (%d chars)",
                    document_type, len(cleaned_text))

    return documents


def get_related_documents_text(conn, application_number: str) -> list[dict[str, str]]:
    """Returns extracted text from all PDFs associated with a planning application.

    Connects to the RDS database to look up the application's document page URL,
    scrapes the Idox planning portal for PDF links, downloads each PDF, and
    extracts the text content.

    Requires the following environment variables for database connection:
        DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

    Args:
        application_number: The unique reference number (e.g. 'PA/26/00515/NC').

    Returns:
        A list of dicts, each with 'document_type' (str) and 'document_text' (str) keys.
        Returns an empty list if the application is not found or scraping fails.
    """
    '''conn = get_rds_connection(
        rds_host=os.environ["DB_HOST"],
        rds_port=int(os.environ.get("DB_PORT", "5432")),
        rds_user=os.environ["DB_USER"],
        rds_password=os.environ["DB_PASSWORD"],
        rds_db_name=os.environ["DB_NAME"],
    )'''

    document_page_url = get_document_page_url(conn, application_number)

    if not document_page_url:
        logger.error("No document URL found for application: %s",
                     application_number)
        return []

    session = initialise_session()
    if not session:
        return []

    pdf_links = get_pdf_links_from_page(session, document_page_url)
    if not pdf_links:
        logger.info("No PDF documents found for application: %s",
                    application_number)
        return []

    download_dir = Path(tempfile.mkdtemp())

    try:
        documents = extract_document_texts(session, pdf_links, download_dir)
    finally:
        shutil.rmtree(download_dir, ignore_errors=True)

    logger.info(
        "Extracted text from %d documents for application %s",
        len(documents), application_number,
    )
    return documents


if __name__ == "__main__":
    load_dotenv()  # Ensure environment variables are loaded from .env file

    conn = get_rds_connection(
        rds_host=os.environ.get("DB_HOST", "your-db-host"),
        rds_port=int(os.environ.get("DB_PORT", "5432")),
        rds_user=os.environ.get("DB_USER", "your-db-user"),
        rds_password=os.environ.get("DB_PASSWORD", "your-db-password"),
        rds_db_name=os.environ.get("DB_NAME", "your-db-name"),
    )

    application_number = "PA/26/00515/NC"
    document_url = get_document_page_url(conn, application_number)
    print(f"Document URL for {application_number}: {document_url}")

    document_text_for_application = get_related_documents_text(conn,
        application_number)
    for doc in document_text_for_application:
        print(f"Document Type: {doc['document_type']}")
        print(f"Document Text: {doc['document_text'][:500]}...")
    conn.close()
