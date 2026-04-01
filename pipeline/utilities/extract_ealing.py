"""
Extract module for the Ealing planning application scraper.

Handles session management, search result pagination, application detail
parsing (summary + documents), and orchestration of the full scrape pipeline.

Supports two scrape sources:
  - Current applications  (via the rolling current-list search)
  - Weekly decided list   (via the weekly list form, filtered by decided date)
"""

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import urllib3
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
from bs4.element import Tag


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://pam.ealing.gov.uk/online-applications/"

WEEKLY_LIST_SEARCH_URL = f"{BASE_URL}search.do?action=weeklyList"
WEEKLY_LIST_POST_URL = f"{BASE_URL}weeklyListResults.do?action=firstPage"
CURRENT_LIST_SEARCH_URL = f"{BASE_URL}search.do?action=advanced"
CURRENT_LIST_POST_URL = f"{BASE_URL}currentListResults.do?action=firstPage"

# Mappings for extracting fields from the Summary and Further Details tables
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

# Filter value sent with the weekly list POST to request decided applications
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
    """Hits the specified URL to establish the initial JSESSIONID cookie."""
    logger.info("Acquiring fresh JSESSIONID...")
    try:
        session.get(url, timeout=20)
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
    if not csrf_input:
        return None
    value = csrf_input.get("value")
    return value if isinstance(value, str) else None


def parse_available_weeks(html_content: str) -> List[str]:
    """
    Extracts available week values from the weekly list search form.

    Returns Monday date strings in ``"D Mon YYYY"`` format (e.g. ``"30 Mar 2026"``),
    ordered newest-first.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    week_select = soup.find("select", {"name": "week"})

    if not week_select or not isinstance(week_select, Tag):
        logger.warning(
            "Could not find 'week' dropdown in weekly list search form")
        return []

    return [value for opt in week_select.find_all("option") if (value := opt.get("value"))]


def _is_server_error(html_content: str) -> bool:
    """Returns True if the server responded with a session timeout or error page."""
    if "session has timed out" in html_content.lower():
        return True
    soup = BeautifulSoup(html_content, "html.parser")
    if soup.title and soup.title.string:
        return "error" in soup.title.string.lower()
    return False


# ---------------------------------------------------------------------------
# Network Helpers
# ---------------------------------------------------------------------------

def fetch_page(session: requests.Session, url: str) -> Optional[str]:
    """GETs a URL and returns the HTML content, or None on failure."""
    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        return response.text
    except RequestException as e:
        logger.error("Request failed for URL %s: %s", url, e)
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
        return session.post(url, data=payload, timeout=20)
    except RequestException as e:
        logger.error("Network error posting to %s: %s", url, e)
        return None


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

def prime_weekly_decided_state(session: requests.Session, week: str, date_type: str) -> bool:
    """
    Establishes server-side search state for the weekly list.

    Selects the specified week and date type. After a successful call,
    ``pagedSearchResults.do`` will return applications for that week and date type.
    """
    logger.info(
        "Priming server state for weekly list (week: %s, date_type: %s)...", week, date_type)

    search_html = fetch_page(session, WEEKLY_LIST_SEARCH_URL)
    if not search_html:
        logger.error("Failed to retrieve the web page HTML")
        return False

    csrf_token = extract_csrf_token(search_html)
    if not csrf_token:
        logger.error(
            "Could not extract CSRF token from weekly list search page")
        return False

    payload = {
        "_csrf":      csrf_token,
        "week":       week,
        "dateType":   date_type,
        "searchType": "Application",
    }

    success = _post_and_validate(
        session, WEEKLY_LIST_POST_URL, payload,
        referer=WEEKLY_LIST_SEARCH_URL,
        context=f"weekly list priming (week: {week}, date_type: {date_type})",
    )

    if success:
        logger.info(
            "Weekly list server state primed for week: %s, date_type: %s", week, date_type)
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
    url = app_data.get("url")
    if not url:
        return "N/A"
    return _modify_app_url(url, tab_name)


# ---------------------------------------------------------------------------
# Search Results Parsing
# ---------------------------------------------------------------------------

def extract_application_id(app_html: Tag) -> str:
    """Extracts the application reference number from a single search result element.

    Meta tag example: <p class="metaInfo">Ref. No: PA/22/01234 | Validated: 01/01/2022</p>
    """
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
    if not link_tag:
        return "N/A"
    href = link_tag.get("href")
    if not href:
        return "N/A"
    return urljoin(BASE_URL, href)


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
    field_mapping: Dict[str, str],
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

        if len(cols) < 5:
            continue

        document_type = cols[2].get_text(strip=True)
        view_link_tag = cols[-1].find("a", href=True)

        if not view_link_tag:
            continue

        pdf_documents.append({
            "pdf_url":       urljoin(current_page_url, view_link_tag["href"]),
            "document_type": document_type,
        })

    return pdf_documents


# ---------------------------------------------------------------------------
# Shared Pagination Helper
# ---------------------------------------------------------------------------

def paginate_applications_helper(
    session: requests.Session,
    reprime_fn,
    page_limit: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Iterates Idox paginated results until exhaustion.

    Stops when:
    - ``page_limit`` is reached (if provided)
    - a request fails
    - the session cannot be re-primed after a timeout
    - no results are returned
    - an invalid "overflow" page is detected (more than 10 results)

    Returns a flat list of ``{"application_id", "url"}`` dicts.
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

        if not results:
            logger.info("No applications on page %d. Ending pagination.", page)
            break

        if len(results) > 10:
            logger.info(
                "Overflow page detected on page %d. Ending pagination.", page)
            break

        applications.extend(results)
        page += 1

    if page_limit and page > page_limit:
        logger.info("Page limit of %d reached.", page_limit)

    return applications


# ---------------------------------------------------------------------------
# Scraping Orchestration
# ---------------------------------------------------------------------------

def get_weekly_decided_applications(
    session: requests.Session,
    app_limit: Optional[int] = None,
) -> List[Dict[str, str]]:
    """
    Paginates through the weekly list search result pages for both decided and validated applications,
    scraping all available weeks, returning application stubs.

    Args:
        session: Requests session for HTTP calls
        app_limit: Optional limit on total applications to return per date type. Set to 10 for testing.
    """
    if not acquire_session_cookie(session, WEEKLY_LIST_SEARCH_URL):
        logger.error("Failed to acquire session cookie. Exiting.")
        return []

    # Fetch available weeks
    search_html = fetch_page(session, WEEKLY_LIST_SEARCH_URL)
    if not search_html:
        logger.error("Failed to retrieve weeks list")
        return []

    weeks = parse_available_weeks(search_html)
    if not weeks:
        logger.error("No weeks available in weekly list dropdown")
        return []

    logger.info(
        "Found %d weeks available. Scraping validated (10 weeks) and decided (3 weeks)", len(weeks))

    all_applications: List[Dict[str, str]] = []

    # Loop through date types first (validated first), then weeks with appropriate limits
    for date_type in [DATE_TYPE_VALIDATED, DATE_TYPE_DECIDED]:
        if date_type == DATE_TYPE_VALIDATED:
            week_limit = 6
        else:
            week_limit = 3
        weeks_to_scrape = weeks[:week_limit]

        date_type_apps: List[Dict[str, str]] = []

        logger.info("Scraping %s applications from %d weeks",
                    date_type, len(weeks_to_scrape))

        for week in weeks_to_scrape:
            # Stop if we've reached the limit for this date type
            if app_limit and len(date_type_apps) >= app_limit:
                logger.info(
                    "Reached app_limit of %d for %s. Stopping.", app_limit, date_type)
                break

            logger.info("Scraping week: %s, date_type: %s", week, date_type)

            if not prime_weekly_decided_state(session, week, date_type):
                logger.error(
                    "Failed to prime weekly list server state for week: %s, date_type: %s. Skipping.",
                    week, date_type)
                continue

            # Create a closure that captures the current week and date_type
            def reprime_fn(w=week, dt=date_type):
                return prime_weekly_decided_state(session, w, dt)

            page_results = paginate_applications_helper(session, reprime_fn)

            # If app_limit is set, truncate results to not exceed limit for this date type
            if app_limit:
                remaining = app_limit - len(date_type_apps)
                page_results = page_results[:remaining]

            date_type_apps.extend(page_results)
            all_applications.extend(page_results)
            logger.info("Added %d applications from week: %s, date_type: %s. Total for %s: %d",
                        len(page_results), week, date_type, date_type, len(date_type_apps))

    logger.info("Total applications scraped: %d", len(all_applications))
    return all_applications


def enrich_application(
    session: requests.Session,
    application: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Visits a single application's summary, details, and documents pages.

    Returns a fully enriched data dictionary, or None if the primary summary
    fetch fails. The ``database_action`` field ("insert" or "update") is
    carried forward from the stub produced by ``filter_new_applications``.
    """
    app_id = application.get("application_id", "Unknown ID")
    logger.info("Enriching data for application: %s", app_id)

    # 1. Summary tab (primary data — abort if this fails)
    summary_url = get_tab_url(application, "summary")
    summary_html = fetch_page(session, summary_url)
    if not summary_html:
        logger.error("[%s] Failed to fetch summary page", app_id)
        return None
    summary_data = parse_summary_page(summary_html)

    # 2. Further Details tab (application type)
    details_url = get_tab_url(application, "details")
    details_html = fetch_page(session, details_url)
    if details_html:
        summary_data["application_type"] = parse_further_details_page(
            details_html)
    else:
        logger.warning(
            "[%s] Failed to fetch details page. Defaulting App Type", app_id)
        summary_data["application_type"] = "N/A"

    # 3. Documents tab
    documents_url = get_tab_url(application, "documents")
    documents_html = fetch_page(session, documents_url)
    if documents_html:
        pdf_data = parse_documents_page(
            documents_html, current_page_url=documents_url)
    else:
        logger.warning("[%s] Failed to fetch documents page", app_id)
        pdf_data = []

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

    enriched = []
    for index, app in enumerate(applications, start=1):
        logger.debug("Processing %d/%d", index, total)
        result = enrich_application(session, app)
        if result:
            enriched.append(result)

    logger.info("Enrichment complete. %d/%d succeeded", len(enriched), total)
    return enriched


# ---------------------------------------------------------------------------
# Database Helpers
# ---------------------------------------------------------------------------

def get_existing_applications(conn: Any) -> Dict[str, Dict[str, str]]:
    """
    Retrieves applications already stored in the database as a dict mapping
    ``application_number`` → ``{"status": ..., "decision_type": ...}``,
    for fast lookup of existence, current status, and decision.
    """
    if conn is None:
        logger.warning(
            "No database connection provided. Skipping existing application check.")
        return {}

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT a.application_number, s.status_type, d.decision_type
            FROM application a
            JOIN status_type s ON a.status_type_id = s.status_type_id
            LEFT JOIN decision_type d ON a.decision_type_id = d.decision_type_id
        """)
        return {
            row[0]: {"status": row[1], "decision_type": row[2]}
            for row in cursor.fetchall()
        }


def filter_new_applications(
    initial_application_info: List[Dict[str, str]],
    existing_applications: Dict[str, Dict[str, str]],
) -> List[Dict[str, str]]:
    """
    Filters application info to return only new applications (not in the database).

    Returns a list of initial application info annotated with ``database_action: "insert"``.
    This is called *before* enrichment to avoid unnecessary work on existing applications.
    """
    new_apps = []

    for app_info in initial_application_info:
        app_id = app_info["application_id"]

        if app_id not in existing_applications:
            logger.info("New application found: %s", app_id)
            new_apps.append({**app_info, "database_action": "insert"})
        else:
            logger.debug(
                "Application already exists, will check for changes: %s", app_id)

    logger.info("Filter new: %d new out of %d total applications",
                len(new_apps), len(initial_application_info))
    return new_apps


def _normalise(value: Optional[str]) -> str:
    """Lowercase and strip a string for case-insensitive comparison."""
    if not value:
        return ""
    return value.strip().lower()


def _has_application_changed(
    scraped_app: Dict[str, Any],
    stored: Dict[str, str],
) -> bool:
    """Return True if the scraped status or decision differs from the stored values."""
    if _normalise(scraped_app.get("status")) != _normalise(stored.get("status")):
        return True
    if _normalise(scraped_app.get("decision")) != _normalise(stored.get("decision_type")):
        return True
    return False


def filter_changed_applications(
    enriched_apps: List[Dict[str, Any]],
    existing_applications: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    """
    Filters enriched applications to return only those whose status or decision
    has changed.

    Comparisons are case-insensitive to avoid false positives from casing
    differences between the scraper and the database.

    Returns a list of enriched applications annotated with ``database_action: "update"``.
    This is called *after* enrichment so we can compare scraped values with the
    values stored in the database.
    """
    changed_apps = []
    unchanged_apps = []

    for app in enriched_apps:
        app_id = app["application_number"]

        if app_id not in existing_applications:
            logger.debug(
                "Application not in database (should not happen in filter_changed): %s", app_id)
            continue

        stored = existing_applications[app_id]

        if not _has_application_changed(app, stored):
            logger.debug("No changes detected for %s", app_id)
            unchanged_apps.append(app_id)
            continue

        logger.info(
            "Change detected for %s: status '%s' → '%s', decision '%s' → '%s'",
            app_id,
            stored.get("status"), app.get("status"),
            stored.get("decision_type"), app.get("decision"),
        )
        changed_apps.append({**app, "database_action": "update"})

    logger.info("Filter changed: %d changed, %d unchanged out of %d existing applications",
                len(changed_apps), len(unchanged_apps), len(enriched_apps))
    return changed_apps


# ---------------------------------------------------------------------------
# Pipeline Runners
# ---------------------------------------------------------------------------

def _run_scraper_pipeline(
    conn: Any,
    scraper_to_run,
    label: str,
    scraper_kwargs: dict = None,
) -> List[Dict[str, Any]]:
    """
    Shared pipeline: create session → fetch stubs → filter new (pre-enrichment)
    → enrich new → filter changed (post-enrichment) → return applications that
    need inserting or updating.

    Args:
        scraper_kwargs: Optional dict of keyword arguments to pass to scraper_to_run()
    """
    if scraper_kwargs is None:
        scraper_kwargs = {}

    session = create_scraper_session()
    existing = get_existing_applications(conn)
    logger.info("Database contains %d existing applications", len(existing))

    logger.info("Starting scrape for %s", label)

    initial_application_info = scraper_to_run(session, **scraper_kwargs)
    logger.info("Scraper returned %d applications for %s",
                len(initial_application_info), label)

    # Filter new applications before enrichment to avoid unnecessary work
    new_info = filter_new_applications(initial_application_info, existing)

    # Enrich only the new applications
    if new_info:
        logger.info("Enriching %d new applications", len(new_info))
        enriched_new = enrich_applications(session, new_info)
        logger.info("Enrichment complete: %d of %d new applications enriched successfully",
                    len(enriched_new), len(new_info))
    else:
        enriched_new = []
        logger.info("No new applications to enrich")

    # Filter changed applications: need to enrich existing apps to compare status
    existing_info = [
        s for s in initial_application_info if s["application_id"] in existing]
    if existing_info:
        logger.info(
            "Enriching %d existing applications to check for changes", len(existing_info))
        enriched_existing = enrich_applications(session, existing_info)
        logger.info("Enrichment complete: %d of %d existing applications enriched",
                    len(enriched_existing), len(existing_info))
        changed_apps = filter_changed_applications(enriched_existing, existing)
    else:
        changed_apps = []
        logger.info("No existing applications to check for changes")

    # Combine new and changed applications
    result = enriched_new + changed_apps

    logger.info("Completed scrape for %s: %d new, %d updated, %d total to process",
                label, len(enriched_new), len(changed_apps), len(result))
    return result


def run_scraper_weekly_applications(conn: Any, app_limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Runs the scraper pipeline for weekly decided applications.

    Args:
        app_limit: Optional limit on applications per date type (validated/decided).
                   Useful for testing.
    """

    logger.info("Starting scrape: weekly decided applications")
    scraper_kwargs = {}
    if app_limit is not None:
        scraper_kwargs['app_limit'] = app_limit
        logger.info("Using app_limit: %d applications per date type", app_limit)

    return _run_scraper_pipeline(
        conn,
        scraper_to_run=get_weekly_decided_applications,
        label="weekly applications",
        scraper_kwargs=scraper_kwargs,
    )


if __name__ == "__main__":
    print(run_scraper_weekly_applications(None))
