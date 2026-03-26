"""
Extract module for the Tower Hamlets planning application scraper.

Handles session management, search result pagination, application detail
parsing (summary + documents), and orchestration of the full scrape pipeline.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import urllib3
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from bs4.element import Tag


# --- Configuration ---

BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"

# Mappings for extracting the relevant fields from the Summary and Further Details tables

SUMMARY_FIELD_MAPPING: Dict[str, str] = {
    "Application Validated": "validation_date",
    "Address": "address",
    "Proposal": "description",
    "Status": "status",
}

FURTHER_DETAILS_FIELD_MAPPING: Dict[str, str] = {
    "Application Type": "app_type",
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
    try:
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
    except Exception as e:
        logger.error("Error creating session: %s", e)
        raise


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
    logger.info(f"Success: Captured JSESSIONID ({cookie_preview}...)")
    return True


def extract_csrf_token(html_content: str) -> Optional[str]:
    """
    Parses HTML to find the hidden CSRF security token required for POST requests.
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


def get_tab_url(app_data: Dict[str, str], tab_name: str) -> str:
    """
    Generates the URL for a specific tab (e.g., 'summary', 'documents', 'details')
    from an application's base URL.

    """
    return _modify_app_url(app_data["url"], tab_name)


# ----------------------------------------------
# Search Results Parsing
# ----------------------------------------------


def extract_application_id(app_html: Tag) -> str:
    """Extracts the application reference number from a single search result element.
    Meta tag example: <p class="metaInfo">Ref. No: PA/22/01234 | Validated: 01/01/2022</p>
    """
    # Finds the tag with the class 'metaInfo'
    meta_tag = app_html.find("p", class_="metaInfo")

    if not meta_tag:
        return "N/A"

    # Extracts the text content and splits it by '|' to separate metadata
    meta_parts = meta_tag.text.split("|")
    for part in meta_parts:
        clean_part = " ".join(part.split())
        if clean_part.startswith("Ref. No:"):
            return clean_part.replace("Ref. No:", "").strip()

    return "N/A"


def extract_application_url(app_html: Tag) -> str:
    """Extracts the application detail page URL from a single search result element."""
    link_tag = app_html.find("a")
    if link_tag and link_tag.get("href"):
        return urljoin(BASE_URL, link_tag.get("href"))
    return "N/A"


def parse_search_result(app_html: Tag) -> Dict[str, str]:
    """Extracts the application ID and URL from a single search result element."""
    return {
        "application_id": extract_application_id(app_html),
        "url": extract_application_url(app_html),
    }


def parse_results_page(html_content: str) -> List[Dict[str, str]]:
    """
    Parses a full search results page and returns a list of application dictionaries.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    apps = soup.find_all("li", class_="searchresult")

    logger.info("Found %d search result elements on page", len(apps))

    # For each search result element, extract the application ID and URL using the helper functions
    page_data = [parse_search_result(app) for app in apps]

    for result in page_data:
        logger.debug(
            "Extracted: %s - %s",
            result['application_id'],
            result['url'])

    return page_data


# ----------------------------------------------
# Application Detail Parsing
# ----------------------------------------------


def clean_html_text(element: Optional[Tag]) -> str:
    """Strips whitespace, non-breaking spaces, and extra newlines from an HTML element."""
    if not element:
        return "N/A"
    return " ".join(element.get_text().split()).strip()


def extract_table_metadata(
    soup: BeautifulSoup,
    table_id: str,
    field_mapping: Dict[str, str]
) -> Dict[str, str]:
    """Extracts key metadata fields from a specified table using a field mapping."""
    metadata: Dict[str, str] = {}

    table = soup.find("table", id=table_id)
    if not table or not isinstance(table, Tag):
        logger.warning("Could not find table with ID '%s'", table_id)
        return metadata

    for row in table.find_all("tr"):
        header = row.find("th")
        value = row.find("td")
        if not header or not value:
            continue

        label = clean_html_text(header)
        if label in field_mapping:
            metadata[field_mapping[label]] = clean_html_text(value)

    return metadata


def parse_summary_page(html_content: str) -> Dict[str, str]:
    """Parses an application's summary page HTML for key metadata."""
    soup = BeautifulSoup(html_content, "html.parser")
    return extract_table_metadata(soup, "simpleDetailsTable", SUMMARY_FIELD_MAPPING)


def parse_further_details_page(html_content: str) -> str:
    """Parses the Further Details Tab specifically to get the Application Type."""
    soup = BeautifulSoup(html_content, 'html.parser')
    result = extract_table_metadata(
        soup, "applicationDetails", FURTHER_DETAILS_FIELD_MAPPING)
    return result.get("app_type", "N/A")


def parse_documents_page(html_content: str, current_page_url: str) -> List[Dict[str, str]]:
    """
    Parses the Documents tab to extract PDF URLs and their associated document types.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    documents_table = soup.find("table", id="Documents")

    if not documents_table:
        return []

    pdf_documents: List[Dict[str, str]] = []

    for row in documents_table.find_all("tr"):
        cols = row.find_all("td")

        # Skip header rows or unexpectedly short rows
        if len(cols) < 6:
            continue

        # Hardcoded to standard Idox column indices
        document_type = cols[2].get_text(strip=True)
        view_link_tag = cols[5].find("a", href=True)

        if not view_link_tag:
            continue

        # Build the final URL
        pdf_url = urljoin(current_page_url, view_link_tag["href"])

        pdf_documents.append({
            "pdf_url": pdf_url,
            "document_type": document_type,
        })

    return pdf_documents


# ----------------------------------------------
# Network-level Fetching
# ----------------------------------------------


def fetch_page(session: requests.Session, url: str) -> Optional[str]:
    """
    Fetches a page using the session and returns its HTML content.
    Returns None if the request fails or times out.
    """
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except RequestException as e:
        logger.error("Request failed for URL %s: %s", url, e)
        return None


# ----------------------------------------------
# Scraping Orchestration
# ----------------------------------------------


def get_current_applications(session: requests.Session) -> List[Dict[str, str]]:
    """Paginates through search result pages, returning application stubs."""

    if not acquire_session_cookie(session, BASE_URL) or not prime_session_state(session, BASE_URL):
        logger.error("Failed to initialize session. Exiting.")
        return []

    applications: List[Dict[str, str]] = []

    page = 1
    while True:
        logger.info(f"Fetching Page {page}...")
        url = f"{BASE_URL}pagedSearchResults.do?action=page&searchCriteria.page={page}"
        html_content = fetch_page(session, url)

        if not html_content:
            logger.warning(f"Failed to fetch page {page}.")
            break

        if "session has timed out" in html_content.lower():
            logger.warning(f"Session timed out on page {page}. Re-priming...")
            if not prime_session_state(session, BASE_URL):
                logger.error("Failed to re-prime session state. Stopping.")
                break
            continue

        extracted_apps = parse_results_page(html_content)

        if not extracted_apps:
            logger.info(
                f"No applications found on page {page}. Ending pagination.")
            break

        applications.extend(extracted_apps)
        page += 1

    return applications


def enrich_application(
    session: requests.Session,
    application: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Visits a single application's summary, details, and documents pages.
    Returns a fully enriched data dictionary, or None if primary summary fails.
    """

    app_id = application.get("application_id", "Unknown ID")
    logger.info("Enriching data for application: %s", app_id)

    # 1. Fetch and parse the Summary tab (Primary data)
    summary_url = get_tab_url(application, "summary")
    summary_html = fetch_page(session, summary_url)
    if not summary_html:
        logger.error("[%s] Failed to fetch summary page", app_id)
        return None

    summary_data = parse_summary_page(summary_html)

    # 2. Fetch and parse the Further Details tab (For Application Type)
    details_url = get_tab_url(application, "details")
    details_html = fetch_page(session, details_url)
    if details_html:
        summary_data["application_type"] = parse_further_details_page(
            details_html)
    else:
        logger.warning(
            "[%s] Failed to fetch details page. Defaulting App Type", app_id)
        summary_data["application_type"] = "N/A"

    # 3. Fetch and parse the Documents tab
    documents_url = get_tab_url(application, "documents")
    documents_html = fetch_page(session, documents_url)

    if documents_html:
        pdf_data = parse_documents_page(
            documents_html, current_page_url=documents_url)
    else:
        logger.warning("[%s] Failed to fetch documents page", app_id)
        pdf_data = []

    # 4. Compile and return the enriched payload
    enriched_app: Dict[str, Any] = {
        "application_number": app_id,
        "application_page_url": application.get("url", ""),
        "document_page_url": documents_url,
        "address": summary_data.get("address", ""),
        "description": summary_data.get("description", ""),
        "status": summary_data.get("status", ""),
        "validation_date": summary_data.get("validation_date", ""),
        "application_type": summary_data.get("application_type", ""),
        "pdfs": pdf_data,
    }

    logger.info("Successfully enriched application: %s", app_id)
    return enriched_app


def enrich_applications(
    session: requests.Session,
    applications: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """Iterates through application stubs and enriches each one."""
    total = len(applications)
    logger.info("Starting detailed scrape for %d applications", total)

    enriched: List[Dict[str, Any]] = []
    for index, app in enumerate(applications, start=1):
        logger.debug("Processing %d/%d", index, total)
        if result := enrich_application(session, app):
            enriched.append(result)

    logger.info("Enrichment complete. %d/%d succeeded", len(enriched), total)
    return enriched


# ----------------------------------------------
# Database Helpers
# ----------------------------------------------


def get_existing_application_ids(conn: Any) -> Set[str]:
    """Retrieves application IDs already stored in the database as a fast-lookup Set."""

    with conn.cursor() as cursor:
        cursor.execute("SELECT application_id FROM application")

        return {row[0] for row in cursor.fetchall()}


def filter_new_applications(
    scraped_apps: List[Dict[str, str]],
    existing_ids: Set[str]
) -> List[Dict[str, str]]:
    """Returns only the applications whose IDs are not already in the database."""

    new_apps = [app for app in scraped_apps if app["application_id"]
                not in existing_ids]

    logger.info("Filtered %d new applications to process", len(new_apps))
    return new_apps


# ----------------------------------------------
# Main Orchestrator
# ----------------------------------------------


def run_scraper(conn: Any) -> List[Dict[str, Any]]:
    """
    Main entry point. Sets up a session, scrapes current applications,
    filters out duplicates, and enriches the new ones with detail data.
    """
    session = create_scraper_session()

    current_applications = get_current_applications(session)
    logger.info("Total applications scraped: %d", len(current_applications))

    existing_ids = get_existing_application_ids(conn)
    new_applications = filter_new_applications(
        current_applications, existing_ids)
    logger.info("New applications to enrich: %d", len(new_applications))

    return enrich_applications(session, new_applications)
