"""
Extract module for the Tower Hamlets planning application scraper.

Handles session management, search result pagination, application detail
parsing (summary + documents), and orchestration of the full scrape pipeline.
"""

import logging
import urllib3
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional


# --- Configuration ---

BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"

SUMMARY_FIELD_MAPPING: Dict[str, str] = {
    "Application Validated": "validation_date",
    "Address": "address",
    "Proposal": "description",
    "Status": "status",
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ----------------------------------------------
# Session Management
# ----------------------------------------------


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


def acquire_session_cookie(session: requests.Session) -> bool:
    """Hits the homepage to establish the initial JSESSIONID cookie."""
    logger.info("Acquiring fresh JSESSIONID...")
    session.get(BASE_URL)

    if "JSESSIONID" not in session.cookies:
        logger.error("Failed to capture JSESSIONID.")
        return False

    cookie_preview = session.cookies["JSESSIONID"][:10]
    logger.info(f"Success: Captured JSESSIONID ({cookie_preview}...)")
    return True


def extract_csrf_token(html_content: str) -> Optional[str]:
    """
    Parses HTML to find the hidden CSRF security token required for POST requests.
    Separated from network requests to allow for easy unit testing.
    """
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


def prime_session_state(session: requests.Session) -> bool:
    """
    Navigates the Idox system to establish the server-side search state.
    This requires handling a CSRF token and mimicking a specific form submission.
    """
    logger.info("Priming server state (Handling CSRF & POST)...")
    search_page_url = f"{BASE_URL}search.do?action=advanced"

    # STEP 1: Land on the search page to grab the hidden CSRF token
    get_response = session.get(search_page_url)
    csrf_token = extract_csrf_token(get_response.text)

    if not csrf_token:
        logger.error("Could not find the _csrf token in the page HTML.")
        return False

    logger.debug(f"Found CSRF Token: {csrf_token}")

    # STEP 2: Submit the form data to initialise results
    primer_url = f"{BASE_URL}currentListResults.do?action=firstPage"
    payload = {
        "_csrf": csrf_token,
        "currentListSearch": "true",
        "searchCriteria.currentListSearch": "true",
        "searchType": "Application",
    }

    session.headers.update({"Referer": search_page_url})
    post_response = session.post(primer_url, data=payload)

    # STEP 3: Verify the state was primed successfully
    if _check_for_server_error(post_response.text):
        logger.error("Server returned an error or timeout during priming.")
        return False

    logger.info("Server state primed successfully.")
    return True


# ----------------------------------------------
# URL Construction Helpers
# ----------------------------------------------


def _modify_app_url(url: str, target_tab: str) -> str:
    """Swaps the activeTab query parameter in an Idox application URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["activeTab"] = [target_tab]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def get_summary_url(app_data: Dict[str, str]) -> str:
    """Generates the Summary tab URL from an application's base URL."""
    return _modify_app_url(app_data["url"], "summary")


def get_documents_url(app_data: Dict[str, str]) -> str:
    """Generates the Documents tab URL from an application's base URL."""
    return _modify_app_url(app_data["url"], "documents")


# ----------------------------------------------
# Search Results Parsing
# ----------------------------------------------


def extract_application_id(app_html) -> str:
    """Extracts the application reference number from a single search result element."""
    meta_tag = app_html.find("p", class_="metaInfo")
    if not meta_tag:
        return "N/A"

    meta_parts = meta_tag.text.split("|")
    for part in meta_parts:
        clean_part = " ".join(part.split())
        if clean_part.startswith("Ref. No:"):
            return clean_part.replace("Ref. No:", "").strip()

    return "N/A"


def extract_application_url(app_html) -> str:
    """Extracts the application detail page URL from a single search result element."""
    link_tag = app_html.find("a")
    if link_tag and link_tag.get("href"):
        return urljoin(BASE_URL, link_tag.get("href"))
    return "N/A"


def parse_search_result(app_html) -> Dict[str, str]:
    """Extracts the application ID and URL from a single search result element."""
    return {
        "application_id": extract_application_id(app_html),
        "url": extract_application_url(app_html),
    }


def parse_results_page(html_content: str) -> List[Dict[str, str]]:
    """
    Parses a full search results page and returns a list of application stubs
    (each containing an application_id and url).
    """
    soup = BeautifulSoup(html_content, "html.parser")
    apps = soup.find_all("li", class_="searchresult")

    logger.info(f"Found {len(apps)} search result elements on page.")

    page_data: List[Dict[str, str]] = []
    for app in apps:
        result = parse_search_result(app)
        page_data.append(result)
        logger.debug(f"Extracted: {result['application_id']} - {result['url']}")

    return page_data


# ----------------------------------------------
# Application Detail Parsing
# ----------------------------------------------


def clean_html_text(element) -> str:
    """Strips whitespace, non-breaking spaces, and extra newlines from an HTML element."""
    if not element:
        return "N/A"
    return " ".join(element.get_text().split()).strip()


def extract_summary_metadata(soup: BeautifulSoup) -> Dict[str, str]:
    """Extracts key metadata fields from the simpleDetailsTable on a summary page."""
    metadata: Dict[str, str] = {}

    table = soup.find("table", id="simpleDetailsTable")
    if not table:
        logger.warning("Could not find simpleDetailsTable in the summary page.")
        return metadata

    for row in table.find_all("tr"):
        header = row.find("th")
        value = row.find("td")
        if not header or not value:
            continue

        label = clean_html_text(header)
        if label in SUMMARY_FIELD_MAPPING:
            metadata[SUMMARY_FIELD_MAPPING[label]] = clean_html_text(value)

    return metadata


def parse_summary_page(html_content: str) -> Dict[str, str]:
    """
    Parses an application's summary page HTML and returns a dictionary with
    keys: address, description, status, validation_date.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    return extract_summary_metadata(soup)


def parse_documents_page(html_content: str) -> List[Dict[str, str]]:
    """
    Parses an application's documents page HTML and returns a list of
    dictionaries, each containing a pdf_url and document_type.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    documents_table = soup.find("table", id="Documents")

    if not documents_table:
        logger.debug("No documents table found on this page.")
        return []

    pdf_documents: List[Dict[str, str]] = []
    rows = documents_table.find_all("tr")

    for row in rows:
        cols = row.find_all("td")

        # Columns: [0] Checkbox, [1] Date, [2] Type, [3] Drawing No, [4] Description, [5] View Link
        if len(cols) < 6:
            continue

        document_type = cols[2].get_text(strip=True)
        view_link_tag = cols[5].find("a")

        if not view_link_tag or not view_link_tag.get("href"):
            continue

        pdf_url = urljoin(BASE_URL, view_link_tag.get("href"))
        pdf_documents.append({
            "pdf_url": pdf_url,
            "document_type": document_type,
        })

    logger.debug(f"Successfully extracted {len(pdf_documents)} PDFs.")
    return pdf_documents


# ----------------------------------------------
# Network-level Fetching
# ----------------------------------------------


def fetch_page(session: requests.Session, url: str) -> Optional[str]:
    """
    Fetches a page using the session and returns its HTML content.
    Returns None if the request fails.
    """
    response = session.get(url, timeout=10)
    if response.status_code != 200:
        logger.error(f"Status {response.status_code} for URL: {url}")
        return None
    return response.text


# ----------------------------------------------
# Scraping Orchestration
# ----------------------------------------------


MAX_PAGES = 2  # Safety cap to limit pagination during development


def get_current_applications(session: requests.Session) -> List[Dict[str, str]]:
    """
    Authenticates and paginates through all search result pages,
    returning a list of application stubs (id + url).
    """
    if not acquire_session_cookie(session):
        logger.error("Failed to acquire session cookie. Exiting.")
        return []

    if not prime_session_state(session):
        logger.error("Failed to prime session state. Exiting.")
        return []

    applications: List[Dict[str, str]] = []
    page = 1

    while page <= MAX_PAGES:
        logger.info(f"Fetching Page {page}...")
        url = f"{BASE_URL}pagedSearchResults.do?action=page&searchCriteria.page={page}"
        response = session.get(url)

        if "session has timed out" in response.text.lower():
            logger.warning(f"Session timed out on page {page}. Re-priming...")
            if not prime_session_state(session):
                logger.error("Failed to re-prime session state. Stopping.")
                break
            continue

        extracted_apps = parse_results_page(response.text)

        if not extracted_apps:
            logger.info(f"No applications found on page {page}. Ending pagination.")
            break

        applications.extend(extracted_apps)
        page += 1

    return applications


def enrich_application(session: requests.Session, application: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Visits a single application's summary and documents pages and returns
    a fully enriched data dictionary, or None on failure.
    """
    app_id = application.get("application_id", "Unknown ID")
    logger.info(f"Enriching data for application: {app_id}")

    summary_url = get_summary_url(application)
    summary_html = fetch_page(session, summary_url)
    if not summary_html:
        logger.error(f"[{app_id}] Failed to fetch summary page.")
        return None

    summary_data = parse_summary_page(summary_html)

    documents_url = get_documents_url(application)
    documents_html = fetch_page(session, documents_url)
    if not documents_html:
        logger.error(f"[{app_id}] Failed to fetch documents page.")
        return None

    pdf_data = parse_documents_page(documents_html)

    enriched_app: Dict[str, Any] = {
        "application_number": app_id,
        "source_url": application.get("url", ""),
        "address": summary_data.get("address", ""),
        "postcode": "",  # Placeholder: implement extraction in summary parser later
        "description": summary_data.get("description", ""),
        "status": summary_data.get("status", ""),
        "validation_date": summary_data.get("validation_date", ""),
        "pdfs": pdf_data,
    }

    logger.info(f"Successfully enriched application: {app_id}")
    return enriched_app


def enrich_applications(session: requests.Session, applications: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Iterates through a list of application stubs and enriches each one
    with data from its summary and documents pages.
    """
    total = len(applications)
    logger.info(f"Starting detailed scrape for {total} applications...")

    enriched: List[Dict[str, Any]] = []
    for index, app in enumerate(applications, start=1):
        logger.debug(f"Processing {index}/{total}...")
        result = enrich_application(session, app)
        if result:
            enriched.append(result)

    logger.info(f"Enrichment complete. {len(enriched)}/{total} succeeded.")
    return enriched


# ----------------------------------------------
# Database Helpers
# ----------------------------------------------


def get_existing_application_ids(conn) -> List[str]:
    """Retrieves application IDs already stored in the database."""
    if conn is None:
        return []

    with conn.cursor() as cursor:
        cursor.execute("SELECT application_id FROM applications")
        existing_ids: List[str] = []
        for row in cursor.fetchall():
            existing_ids.append(row[0])

    return existing_ids


def filter_new_applications(
    scraped_apps: List[Dict[str, str]],
    existing_ids: List[str],) -> List[Dict[str, str]]:
    """Returns only the applications whose IDs are not already in the database."""
    new_apps: List[Dict[str, str]] = []
    for app in scraped_apps:
        if app["application_id"] not in existing_ids:
            new_apps.append(app)

    logger.info(f"Filtered {len(new_apps)} new applications to process.")
    return new_apps


# ----------------------------------------------
# Main Orchestrator
# ----------------------------------------------


def run_scraper() -> List[Dict[str, Any]]:
    """
    Main entry point. Sets up a session, scrapes current applications,
    filters out duplicates, and enriches the new ones with detail data.
    """
    session = create_scraper_session()

    current_applications = get_current_applications(session)
    logger.info(f"Total applications scraped: {len(current_applications)}")

    existing_ids = get_existing_application_ids(conn=None)
    new_applications = filter_new_applications(current_applications, existing_ids)
    logger.info(f"New applications to enrich: {len(new_applications)}")

    enriched = enrich_applications(session, new_applications)
    return enriched


if __name__ == "__main__":
    logger.info("Starting Tower Hamlets Scraper...")
    results = run_scraper()
    sample = results[:5]
    logger.info(f"Sample Extracted Applications: {sample}")
    logger.info(f"Scrape Complete! Total applications found: {len(results)}")
