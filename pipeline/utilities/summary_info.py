import logging
from get_urls_for_application import get_summary_url_for_application
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


def extract_table_metadata(soup: BeautifulSoup) -> dict:
    """Focuses only on the <table> with id 'simpleDetailsTable'."""
    metadata = {}
    field_mapping = {
        "Application Validated": "validation_date",
        "Address": "address",
        "Proposal": "description",
        "Status": "status"
    }

    table = soup.find('table', id='simpleDetailsTable')
    if table:
        for row in table.find_all('tr'):
            header = row.find('th')
            value = row.find('td')
            if header and value:
                label = clean_html_text(header)
                if label in field_mapping:
                    metadata[field_mapping[label]] = clean_html_text(value)
    return metadata


def parse_application_summary(html_content: str) -> dict:
    """Main entry point for assembly."""
    soup = BeautifulSoup(html_content, 'html.parser')
    return extract_table_metadata(soup)


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
            else:
                logger.error(
                    f"Status {response.status_code} for URL: {summary_url}")

        except Exception as e:
            logger.error(
                f"An error occurred while scraping {summary_url}: {e}")

    return detailed_results


if __name__ == "__main__":
    logger.info("Starting Detailed Scrape...")
    results = get_full_application_details()

    print("\n--- SCRAPE RESULTS ---")
    for item in results:
        print(item)

    logger.info(f"Successfully processed {len(results)} applications.")
