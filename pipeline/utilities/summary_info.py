import logging
from get_urls_for_application import get_summary_url_for_application, get_further_details_url_for_application
from extract_helpers4 import run_scraper, create_scraper_session
from bs4 import BeautifulSoup
import re


# Setup logging to see the progress in the console
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def clean_html_text(element) -> str:
    """Strips whitespace, handles &nbsp;, and removes extra newlines."""
    if not element:
        return "N/A"
    return " ".join(element.get_text().split()).strip()


def extract_table_metadata(soup: BeautifulSoup, field_mapping: dict, table_id: str) -> dict:
    """
    Generic extractor that finds a table and maps headers to keys 
    based on the provided field_mapping.
    """
    metadata = {}
    table = soup.find('table', id=table_id)

    if table:
        for row in table.find_all('tr'):
            header = row.find('th')
            value = row.find('td')
            if header and value:
                label = clean_html_text(header)
                if label in field_mapping:
                    metadata[field_mapping[label]] = clean_html_text(value)
    return metadata

# --- Specific Parsers ---


def parse_application_summary(html_content: str) -> dict:
    """Parses the Summary Tab."""
    soup = BeautifulSoup(html_content, 'html.parser')
    mapping = {
        "Application Validated": "validation_date",
        "Address": "address",
        "Proposal": "description",
        "Status": "status"
    }
    return extract_table_metadata(soup, mapping, "simpleDetailsTable")


def parse_further_details(html_content: str) -> str:
    """
    Parses the Further Details Tab specifically to get the Application Type.
    Returns just the string value.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    mapping = {"Application Type": "app_type"}

    result = extract_table_metadata(soup, mapping, "applicationDetails")
    # Return the specific string, or "N/A" if not found
    return result.get("app_type", "N/A")


def get_full_application_details():
    """
    Orchestrates the scraping process by combining network 
    sessions with HTML parsing logic.
    """
    # 1. Initialize the authenticated session
    session = create_scraper_session()

    # 2. Get the list of apps from the initial search results
    # run_scraper handles the JSESSIONID and initial POST priming
    apps = run_scraper()

    if not apps:
        logger.warning("No applications found to process.")
        return []

    detailed_results = []
    application_types = []

    # 3. Iterate through each discovered application
    for app in apps:
        # Generate the specific Summary Tab URL
        summary_url = get_summary_url_for_application(app)

        try:
            logger.info(
                f"Fetching details for Ref: {app.get('application_id')}")
            response = session.get(summary_url, timeout=10)

            if response.status_code == 200:
                # Use the abstracted parser to extract the data
                details = parse_application_summary(response.text)
                detailed_results.append(details)
                logger.info(
                    f"Extracted details for Ref: {app.get('application_id')}")
            else:
                logger.error(
                    f"Status {response.status_code} for URL: {summary_url}")

        except Exception as e:
            logger.error(
                f"An error occurred while scraping {summary_url}: {e}")

        further_detail_url = get_further_details_url_for_application(app)
        logger.info(
            f"Fetching further details for Ref: {app.get('application_id')}")
        response = session.get(further_detail_url, timeout=10)

        if response.status_code == 200:
            app_type = parse_further_details(response.text)
            application_types.append(app_type)
            logger.info(
                f"Extracted application type for Ref: {app.get('application_id')}")
        else:
            logger.error(
                f"Status {response.status_code} for URL: {further_detail_url}")

    return detailed_results, application_types


if __name__ == "__main__":
    logger.info("Starting Detailed Scrape...")
    results, application_types = get_full_application_details()

    print("\n--- SCRAPE RESULTS ---")
    for item in results:
        print(item)
    print("\n--- APPLICATION TYPES ---")
    print(application_types)

    logger.info(f"Successfully processed {len(results)} applications.")
