"""
Extract module for the Tower Hamlets planning application scraper.

Handles session management, search result pagination, application detail
parsing (summary + documents), and orchestration of the full scrape pipeline.

Supports two scrape sources:
  - Current applications  (via the rolling current-list search)
  - Weekly decided list   (via the weekly list form, filtered by decided date)
"""

import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import urllib3
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from bs4.element import Tag


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"

WEEKLY_LIST_SEARCH_URL = f"{BASE_URL}search.do?action=weeklyList"
WEEKLY_LIST_POST_URL = f"{BASE_URL}weeklyListResults.do?action=firstPage"
CURRENT_LIST_SEARCH_URL = f"{BASE_URL}search.do?action=advanced"
CURRENT_LIST_POST_URL = f"{BASE_URL}currentListResults.do?action=firstPage"

# Mappings for extracting the relevant fields from the Summary and Further Details tables
SUMMARY_FIELD_MAPPING: Dict[str, str] = {
    "Application Validated": "validation_date",
    "Address":               "address",
    "Proposal":              "description",
    "Status":                "status",
    "Decision":              "decision",
    "Decision Issued Date":  "decision_date",
}

FURTHER_DETAILS_FIELD_MAPPING: Dict[str, str] = {
    "Application Type": "app_type",
}

# Filter values from button inputs on the weekly list form (is included with the post request)
DATE_TYPE_DECIDED = "DC_Decided"
DATE_TYPE_VALIDATED = "DC_Validated"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

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

    logger.info("Success: Captured JSESSIONID (%s...)",
                session.cookies["JSESSIONID"][:10])
    return True


# ---------------------------------------------------------------------------
# HTML Parsing Helpers
# ---------------------------------------------------------------------------


def extract_csrf_token(html_content: str) -> Optional[str]:
    """Parses HTML to find the hidden _csrf token required for POST requests."""
    soup = BeautifulSoup(html_content, "html.parser")
    csrf_input = soup.find("input", {"name": "_csrf"})
    if csrf_input and isinstance(csrf_input.get("value"), str):
        return csrf_input.get("value")
    return None


def parse_available_weeks(html_content: str) -> List[str]:
    """
    Extracts the list of available week values from the weekly list search form.

    The dropdown option values are Monday date strings in ``"D Mon YYYY"`` format,
    e.g. ``["30 Mar 2026", "23 Mar 2026", ...]``, ordered newest-first.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    week_select = soup.find("select", {"name": "week"})

    if not week_select or not isinstance(week_select, Tag):
        logger.warning(
            "Could not find 'week' dropdown in weekly list search form")
        return []

    return [opt["value"] for opt in week_select.find_all("option") if opt.get("value")]


def _is_server_error(html_content: str) -> bool:
    """Returns True if the server responded with a session timeout or error page."""
    if "session has timed out" in html_content.lower():
        return True
    soup = BeautifulSoup(html_content, "html.parser")
    return bool(soup.title and "error" in soup.title.string.lower())


# ---------------------------------------------------------------------------
# Network Helpers
# ---------------------------------------------------------------------------


def _get_page(session: requests.Session, url: str) -> Optional[requests.Response]:
    """GETs a page, returning the response or None on network error."""
    try:
        return session.get(url, timeout=10)
    except RequestException as e:
        logger.error("Network error fetching %s: %s", url, e)
        return None


def _post_form(
    session: requests.Session,
    url: str,
    payload: Dict[str, str],
    referer: str,
) -> Optional[requests.Response]:
    """POSTs a form payload with a Referer header, returning the response or None on error."""
    try:
        session.headers.update({"Referer": referer})
        return session.post(url, data=payload, timeout=10)
    except RequestException as e:
        logger.error("Network error posting to %s: %s", url, e)
        return None


def _fetch_csrf_token(session: requests.Session, url: str) -> Optional[str]:
    """GETs a page and extracts its CSRF token, returning None on any failure."""
    response = _get_page(session, url)
    if not response:
        return None
    token = extract_csrf_token(response.text)
    if not token:
        logger.error("Could not find _csrf token at %s", url)
    return token


def _post_and_validate(
    session: requests.Session,
    post_url: str,
    payload: Dict[str, str],
    referer: str,
    context: str,
) -> bool:
    """
    POSTs a form and checks the response for server errors.

    Args:
        context: A short description used in error log messages.
    """
    response = _post_form(session, post_url, payload, referer)
    if not response:
        return False
    if _is_server_error(response.text):
        logger.error("Server returned an error or timeout during %s", context)
        return False
    return True


# ---------------------------------------------------------------------------
# Session Priming
# ---------------------------------------------------------------------------


def prime_session_state(session: requests.Session, url: str) -> bool:
    """Establishes server-side search state for the current-applications list."""
    logger.info("Priming server state (current list)...")

    csrf_token = _fetch_csrf_token(session, CURRENT_LIST_SEARCH_URL)
    if not csrf_token:
        return False

    payload = {
        "_csrf":                            csrf_token,
        "currentListSearch":                "true",
        "searchCriteria.currentListSearch": "true",
        "searchType":                       "Application",
    }

    success = _post_and_validate(
        session, CURRENT_LIST_POST_URL, payload,
        referer=CURRENT_LIST_SEARCH_URL,
        context="current list priming",
    )

    if success:
        logger.info("Server state primed successfully")
    return success


def _build_weekly_decided_payload(csrf_token: str, week_value: str) -> Dict[str, str]:
    """Constructs the POST payload for registering a weekly decided list week."""
    return {
        "_csrf":      csrf_token,
        "week":       week_value,
        "dateType":   DATE_TYPE_DECIDED,
        "searchType": "Application",
    }


def prime_weekly_decided_state(session: requests.Session, target_date: date) -> bool:
    """
    Establishes server-side search state for the weekly decided list.

    After a successful call, ``pagedSearchResults.do`` will return decided
    applications for the week containing ``target_date``.
    """
    logger.info(
        "Priming server state for weekly decided list (target: %s)...",
        target_date.isoformat(),
    )

    csrf_token = _fetch_csrf_token(session, WEEKLY_LIST_SEARCH_URL)
    if not csrf_token:
        return False

    weeks = parse_available_weeks(
        session.get(WEEKLY_LIST_SEARCH_URL).text)
    week_value = weeks[0]
    if not week_value:
        return False

    payload = _build_weekly_decided_payload(csrf_token, week_value)
    success = _post_and_validate(
        session, WEEKLY_LIST_POST_URL, payload,
        referer=WEEKLY_LIST_SEARCH_URL,
        context="weekly decided list priming",
    )

    if success:
        logger.info(
            "Weekly decided list server state primed for week: %s", week_value)
    return success

# ---------------------------------------------------------------------------
# URL Construction Helpers
# ---------------------------------------------------------------------------


def _modify_app_url(url: str, target_tab: str) -> str:
    """Swaps the activeTab query parameter in an Idox application URL."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["activeTab"] = [target_tab]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def get_tab_url(app_data: Dict[str, str], tab_name: str) -> str:
    """
    Generates the URL for a specific tab (e.g. 'summary', 'documents', 'details')
    from an application's base URL.
    """
    return _modify_app_url(app_data["url"], tab_name)


# ---------------------------------------------------------------------------
# Search Results Parsing
# ---------------------------------------------------------------------------


def extract_application_id(app_html: Tag) -> str:
    """Extracts the application reference number from a single search result element.

    Meta tag example: <p class="metaInfo">Ref. No: PA/22/01234 | Validated: 01/01/2022</p>
    """
    # Finds the tag with the class 'metaInfo'
    meta_tag = app_html.find("p", class_="metaInfo")
    if not meta_tag:
        return "N/A"

    for part in meta_tag.text.split("|"):
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
        "url":            extract_application_url(app_html),
    }


def parse_results_page(html_content: str) -> List[Dict[str, str]]:
    """
    Parses a full search results page and returns a list of application stubs.

    Works for both current-applications and weekly-list paginated result pages
    because both use the same ``<li class="searchresult">`` markup.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    apps = soup.find_all("li", class_="searchresult")

    logger.info("Found %d search result elements on page", len(apps))

    # For each search result element, extract the application ID and URL using the helper functions
    page_data = [parse_search_result(app) for app in apps]
    for result in page_data:
        logger.debug("Extracted: %s - %s",
                     result["application_id"], result["url"])

    return page_data


# ---------------------------------------------------------------------------
# Application Detail Parsing
# ---------------------------------------------------------------------------


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
    """Parses the Further Details tab specifically to get the Application Type."""
    soup = BeautifulSoup(html_content, "html.parser")
    result = extract_table_metadata(
        soup, "applicationDetails", FURTHER_DETAILS_FIELD_MAPPING)
    return result.get("app_type", "N/A")


def parse_documents_page(html_content: str, current_page_url: str) -> List[Dict[str, str]]:
    """Parses the Documents tab to extract PDF URLs and their associated document types."""
    soup = BeautifulSoup(html_content, "html.parser")
    documents_table = soup.find("table", id="Documents")

    if not documents_table:
        return []

    pdf_documents: List[Dict[str, str]] = []

    for row in documents_table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 6:
            continue

        document_type = cols[2].get_text(strip=True)
        view_link_tag = cols[5].find("a", href=True)

        if not view_link_tag:
            continue

        pdf_documents.append({
            "pdf_url":       urljoin(current_page_url, view_link_tag["href"]),
            "document_type": document_type,
        })

    return pdf_documents


# ---------------------------------------------------------------------------
# Network-level Fetching
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Shared Pagination Helper
# ---------------------------------------------------------------------------


def paginate_applications_helper(
    session: requests.Session,
    reprime_fn,
    *,
    page_limit: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Iterate Idox paginated results until exhaustion.

    Stops when:
    - page_limit is reached (if provided)
    - a request fails
    - session cannot be re-primed after timeout
    - no results are returned
    - an invalid "overflow" page is detected (>10 results)

    Returns a flat list of {"application_id", "url"} dicts.
    """
    applications: List[Dict[str, str]] = []
    page = 1

    while not page_limit or page <= page_limit:
        logger.info("Fetching page %d...", page)

        url = f"{BASE_URL}pagedSearchResults.do?action=page&searchCriteria.page={page}"
        html = fetch_page(session, url)

        if not html:
            logger.warning("Failed to fetch page %d. Stopping.", page)
            break

        if "session has timed out" in html.lower():
            logger.warning("Session timed out on page %d. Re-priming...", page)
            if not reprime_fn():
                logger.error("Failed to re-prime session. Stopping.")
                break
            continue  # retry same page

        results = parse_results_page(html)

        # Stop conditions
        if not results:
            logger.info("No applications on page %d. Ending pagination.", page)
            break

        # comment out later
        if page > 8:
            break

        applications.extend(extracted_apps)
        page += 1

    if page_limit and page > page_limit:
        logger.info("Page limit of %d reached.", page_limit)

    return applications


# ---------------------------------------------------------------------------
# Scraping Orchestration
# ---------------------------------------------------------------------------


def get_current_applications(session: requests.Session) -> List[Dict[str, str]]:
    """
    Paginates through the current-applications search result pages,
    returning application stubs.
    """
    if not acquire_session_cookie(session, BASE_URL):
        logger.error("Failed to acquire session cookie. Exiting.")
        return []

    if not prime_session_state(session, BASE_URL):
        logger.error("Failed to prime current-list session state. Exiting.")
        return []

    def reprime():
        return prime_session_state(session, BASE_URL)

    # DEVELOPMENT CODE page_limit=3
    return paginate_applications_helper(session, reprime, page_limit=3)


def get_weekly_decided_applications(
    session: requests.Session,
    target_date: Optional[date] = None,
) -> List[Dict[str, str]]:
    """
    Paginates through the weekly decided-list search result pages,
    returning application stubs in the same format as ``get_current_applications``.

    By default scrapes the current week. Pass ``target_date`` to scrape a
    historical week
    """
    if target_date is None:
        target_date = date.today()

    if not acquire_session_cookie(session, BASE_URL):
        logger.error("Failed to acquire session cookie. Exiting.")
        return []

    if not prime_weekly_decided_state(session, target_date):
        logger.error(
            "Failed to prime weekly decided list server state. Exiting.")
        return []

    def reprime():
        return prime_weekly_decided_state(session, target_date)

    return paginate_applications_helper(session, reprime, page_limit=3)


def enrich_application(
    session: requests.Session,
    application: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Visits a single application's summary, details, and documents pages.
    Returns a fully enriched data dictionary, or None if the primary summary fails.

    The ``database_action`` field ("insert" or "update") is carried forward from
    the stub produced by ``filter_new_or_changed_applications``.
    """
    app_id = application.get("application_id", "Unknown ID")
    logger.info("Enriching data for application: %s", app_id)

    # 1. Fetch and parse the Summary tab (primary data)
    summary_url = get_tab_url(application, "summary")
    summary_html = fetch_page(session, summary_url)
    if not summary_html:
        logger.error("[%s] Failed to fetch summary page", app_id)
        return None

    summary_data = parse_summary_page(summary_html)

    # 2. Fetch and parse the Further Details tab (application type)
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
        "application_number":   app_id,
        "application_page_url": application.get("url", ""),
        "document_page_url":    documents_url,
        "address":              summary_data.get("address", ""),
        "description":          summary_data.get("description", ""),
        "status":               summary_data.get("status", ""),
        "validation_date":      summary_data.get("validation_date", ""),
        "application_type":     summary_data.get("application_type", ""),
        "decision":             summary_data.get("decision", ""),
        "decision_date":        summary_data.get("decision_date", ""),
        "database_action":      application.get("database_action", "insert"),
        "pdfs":                 pdf_data,
    }

    logger.info("Successfully enriched application: %s", app_id)
    return enriched_app


def enrich_applications(
    session: requests.Session,
    applications: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Iterates through application stubs and enriches each one."""
    total = len(applications)
    logger.info("Starting detailed scrape for %d applications", total)

    count = 0
    enriched: List[Dict[str, Any]] = []
    for index, app in enumerate(applications, start=1):
        logger.debug("Processing %d/%d", index, total)
        if result := enrich_application(session, app):
            enriched.append(result)
            count += 1
        # DEVELOPMENT CODE - remove later
        # if count > 3:
        #    logger.info("Reached limit of 3 applications. Stopping.")
        #    break

    logger.info("Enrichment complete. %d/%d succeeded", len(enriched), total)
    return enriched


# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------


def get_existing_applications(conn: Any) -> Dict[str, str]:
    """
    Retrieves applications already stored in the database as a dict mapping
    application_number -> status, for fast lookup of both existence and current status.
    """
    if conn is None:
        logger.warning(
            "No database connection provided. Skipping existing application check."
        )
        return {}

    with conn.cursor() as cursor:
        cursor.execute("SELECT application_number, status FROM application")
        return {row[0]: row[1] for row in cursor.fetchall()}


def filter_new_or_changed_applications(
    scraped_apps: List[Dict[str, Any]],
    existing_applications: Dict[str, str],
) -> List[Dict[str, Any]]:
    """
    Returns applications that are either new (not yet in the database) or whose
    status has changed since the last scrape.

    Each returned stub is annotated with a ``database_action`` key set to either
    ``"insert"`` (new application) or ``"update"`` (status changed).
    """
    to_process = []

    for app in scraped_apps:
        app_id = app["application_id"]
        if app_id not in existing_applications:
            logger.debug("New application: %s", app_id)
            to_process.append({**app, "database_action": "insert"})

        elif app.get("status") != existing_applications[app_id]:
            logger.debug(
                "Status changed for %s: '%s' -> '%s'",
                app_id,
                existing_applications[app_id],
                app.get("status"),
            )
            to_process.append({**app, "database_action": "update"})

    logger.info("Found %d applications to process", len(to_process))
    return to_process


def run_scraper(conn: Any) -> List[Dict[str, Any]]:
    """Runs the full scraping pipeline and returns enriched application data."""
    session = create_scraper_session()

    # # Step 1: Scrape current applications
    # logger.info("Starting scrape of current applications...")
    # current_applications = get_current_applications(session)
    existing_applications = get_existing_applications(conn)
    # new_current_apps = filter_new_or_changed_applications(
    #     current_applications, existing_applications)
    # enriched_current_apps = enrich_applications(session, new_current_apps)

    logger.info("Starting scrape of weekly applications...")
    # Step 2: Scrape weekly decided applications for the past week
    target_date = date.today() - timedelta(days=14)
    weekly_applications = get_weekly_decided_applications(session, target_date)
    new_weekly_apps = filter_new_or_changed_applications(
        weekly_applications, existing_applications)
    enriched_weekly_apps = enrich_applications(session, new_weekly_apps)

    # Combine and return all enriched applications
    all_enriched = enriched_weekly_apps
    logger.info("Total enriched applications from both sources: %d",
                len(all_enriched))
    return all_enriched


if __name__ == "__main__":
    # For standalone testing of the scraper logic without DB integration
    print(run_scraper(None))
