"""
Extract module for the Tower Hamlets planning application scraper.

Handles session management, search result pagination, application detail
parsing (summary + documents), and orchestration of the full scrape pipeline.
"""

import logging
import pprint
import urllib3
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from bs4.element import Tag  # REFACTOR: Imported Tag for proper typing of parsed HTML elements
from typing import Any, Dict, List, Optional, Set


import re



# --- Configuration ---

BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"

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
        logger.error(f"Network error acquiring cookie: {e}")
        return False

    if "JSESSIONID" not in session.cookies:
        logger.error("Failed to capture JSESSIONID.")
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
            logger.error("Could not find the _csrf token in the page HTML.")
            return False

        logger.debug(f"Found CSRF Token: {csrf_token}")

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
            logger.error("Server returned an error or timeout during priming.")
            return False

        logger.info("Server state primed successfully.")
        return True
    except RequestException as e:
        logger.error(f"Network error during session priming: {e}")
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
    
    # REFACTOR: Consolidated get_summary_url, get_documents_url, etc. 
    # into a single DRY function.
    """
    return _modify_app_url(app_data["url"], tab_name)


# ----------------------------------------------
# Search Results Parsing
# ----------------------------------------------


def extract_application_id(app_html: Tag) -> str:
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
    Parses a full search results page and returns a list of application stubs.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    apps = soup.find_all("li", class_="searchresult")

    logger.info(f"Found {len(apps)} search result elements on page.")

    # REFACTOR: Used list comprehension for cleaner extraction
    page_data = [parse_search_result(app) for app in apps]
    
    for result in page_data:
        logger.debug(f"Extracted: {result['application_id']} - {result['url']}")

    return page_data


# ----------------------------------------------
# Application Detail Parsing
# ----------------------------------------------


def clean_html_text(element: Optional[Tag]) -> str:
    """Strips whitespace, non-breaking spaces, and extra newlines from an HTML element."""
    if not element:
        return "N/A"
    return " ".join(element.get_text().split()).strip()


def extract_table_metadata(soup: BeautifulSoup, table_id: str, field_mapping: Dict[str, str]) -> Dict[str, str]:
    """Extracts key metadata fields from a specified table using a field mapping."""
    metadata: Dict[str, str] = {}

    table = soup.find("table", id=table_id)
    if not table or not isinstance(table, Tag):
        logger.warning(f"Could not find table with ID '{table_id}'.")
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
    result = extract_table_metadata(soup, "applicationDetails", FURTHER_DETAILS_FIELD_MAPPING)
    return result.get("app_type", "N/A")


def parse_documents_page(html_content: str, current_page_url: str) -> List[Dict[str, str]]:
    """
    Parses an application's documents page HTML and returns a list of
    dictionaries, each containing a pdf_url and document_type.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    documents_table = soup.find("table", id="Documents")

    if not documents_table or not isinstance(documents_table, Tag):
        logger.debug("No documents table found on this page.")
        return []

    pdf_documents: List[Dict[str, str]] = []
    
    # 1. Dynamically find column indices from headers (Accounts for guest vs logged-in views)
    headers = [th.get_text(strip=True).lower() for th in documents_table.find_all("th")]
    
    try:
        type_idx = headers.index("document type")
    except ValueError:
        type_idx = 1  # Fallback to standard Idox index
        
    try:
        view_idx = headers.index("view")
    except ValueError:
        view_idx = -1 # Fallback to the last column in the table

    rows = documents_table.find_all("tr")

    for row in rows:
        cols = row.find_all("td")
        if not cols:
            continue  # Skip header row or empty rows

        # 2. Safely extract document type using the dynamic index
        document_type = "Unknown"
        if len(cols) > type_idx:
            document_type = cols[type_idx].get_text(strip=True)

        # 3. Locate the View link dynamically
        view_link_tag = None
        if len(cols) > view_idx:
            view_link_tag = cols[view_idx].find("a", href=True)
            
        # Fallback: Just grab the last link in the row if the layout is entirely unexpected
        if not view_link_tag:
            all_links = row.find_all("a", href=True)
            if all_links:
                view_link_tag = all_links[-1]

        if not view_link_tag or not view_link_tag.get("href"):
            continue
            
        raw_href = view_link_tag.get("href")
        
        # 4. Strip ephemeral session tokens that break links after the scraper finishes
        clean_href = re.sub(r";jsessionid=[a-zA-Z0-9]+", "", raw_href, flags=re.IGNORECASE)

        # 5. Join using the actual page URL, not the static BASE_URL
        pdf_url = urljoin(current_page_url, clean_href)
        
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
    Returns None if the request fails or times out.
    """
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status() # REFACTOR: Automatically catch 4xx/5xx errors
        return response.text
    except RequestException as e:
        logger.error(f"Request failed for URL {url}: {e}")
        return None


# ----------------------------------------------
# Scraping Orchestration
# ----------------------------------------------


MAX_PAGES = 1  # Safety cap to limit pagination during development


def get_current_applications(session: requests.Session) -> List[Dict[str, str]]:
    """Paginates through search result pages, returning application stubs."""
    if not acquire_session_cookie(session, BASE_URL) or not prime_session_state(session, BASE_URL):
        logger.error("Failed to initialize session. Exiting.")
        return []

    applications: List[Dict[str, str]] = []
    page = 1

    while page <= MAX_PAGES:
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
            logger.info(f"No applications found on page {page}. Ending pagination.")
            break

        applications.extend(extracted_apps)
        page += 1

    return applications


def enrich_application(session: requests.Session, application: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """
    Visits a single application's summary, details, and documents pages.
    Returns a fully enriched data dictionary, or None if the primary summary fetch fails.
    """
    app_id = application.get("application_id", "Unknown ID")
    logger.info(f"Enriching data for application: {app_id}")

    # 1. Fetch and parse the Summary tab (Primary data)
    summary_url = get_tab_url(application, "summary")
    summary_html = fetch_page(session, summary_url)
    if not summary_html:
        logger.error(f"[{app_id}] Failed to fetch summary page.")
        return None

    summary_data = parse_summary_page(summary_html)

    # 2. Fetch and parse the Further Details tab (For Application Type)
    details_url = get_tab_url(application, "details")
    details_html = fetch_page(session, details_url)
    if details_html:
        summary_data["application_type"] = parse_further_details_page(details_html)
    else:
        logger.warning(f"[{app_id}] Failed to fetch details page. Defaulting App Type.")
        summary_data["application_type"] = "N/A"

    # 3. Fetch and parse the Documents tab 
    documents_url = get_tab_url(application, "documents")
    documents_html = fetch_page(session, documents_url)
    
    if documents_html:
        # REFACTOR: Pass the documents_url into the parser to construct accurate absolute links
        pdf_data = parse_documents_page(documents_html, current_page_url=documents_url)
    else:
        logger.warning(f"[{app_id}] Failed to fetch documents page.")
        pdf_data = []

    # 4. Compile and return the enriched payload
    enriched_app: Dict[str, Any] = {
        "application_number": app_id,
        "source_url": application.get("url", ""),
        "document_page_url": documents_url,
        "address": summary_data.get("address", ""),
        "description": summary_data.get("description", ""),
        "status": summary_data.get("status", ""),
        "validation_date": summary_data.get("validation_date", ""),
        "application_type": summary_data.get("application_type", ""),
        "pdfs": pdf_data,
    }

    logger.info(f"Successfully enriched application: {app_id}")
    return enriched_app


def enrich_applications(session: requests.Session, applications: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Iterates through application stubs and enriches each one."""
    total = len(applications)
    logger.info(f"Starting detailed scrape for {total} applications...")
    
    enriched: List[Dict[str, Any]] = []
    for index, app in enumerate(applications, start=1):
        logger.debug(f"Processing {index}/{total}...")
        if result := enrich_application(session, app):
            enriched.append(result)

    logger.info(f"Enrichment complete. {len(enriched)}/{total} succeeded.")
    return enriched


# ----------------------------------------------
# Database Helpers
# ----------------------------------------------


def get_existing_application_ids(conn: Any) -> Set[str]:
    """Retrieves application IDs already stored in the database as a fast-lookup Set."""
    # REFACTOR: Added `Any` typehint for the DB connection (or sqlite3.Connection)
    if conn is None:
        return set()

    with conn.cursor() as cursor:
        cursor.execute("SELECT application_id FROM application")
        # REFACTOR: Using a set comprehension directly for O(1) lookup speeds later
        return {row[0] for row in cursor.fetchall()}


def filter_new_applications(scraped_apps: List[Dict[str, str]], existing_ids: Set[str]) -> List[Dict[str, str]]:
    """Returns only the applications whose IDs are not already in the database."""
    # REFACTOR: Switched existing_ids to a Set and used a list comprehension
    new_apps = [app for app in scraped_apps if app["application_id"] not in existing_ids]

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

    return enrich_applications(session, new_applications)


if __name__ == "__main__":
    logger.info("Starting Tower Hamlets Scraper...")
    results = run_scraper()
    sample = results[:5]
    logger.info(f"Sample Extracted Applications: {sample}")
    pprint.pprint(sample)
    logger.info(f"Scrape Complete! Total applications found: {len(results)}")