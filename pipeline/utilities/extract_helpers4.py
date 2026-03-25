import logging
import urllib3
from urllib.parse import urljoin
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from url_transformers import get_summary_url_for_application, get_documents_url_for_application

# --- Global Configurations ---
BASE_URL = "https://development.towerhamlets.gov.uk/online-applications/"

# Configure professional logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


# ----------------------------------------------
# Sessions logic
# ----------------------------------------------


# Suppress the noisy SSL warnings since we are bypassing verification
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def create_scraper_session() -> requests.Session:
    """
    Initializes a persistent session with standard browser headers and disabled SSL.
    """
    session = requests.Session()
    session.verify = False  # Globally disable SSL verification for this session
    
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:148.0) Gecko/20100101 Firefox/148.0',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Connection': 'keep-alive'
    })
    return session


def acquire_session_cookie(session: requests.Session) -> bool:
    """
    Hits the homepage to establish the initial JSESSIONID cookie.
    """
    logger.info("Acquiring fresh JSESSIONID...")
    session.get(BASE_URL)
    
    if 'JSESSIONID' in session.cookies:
        cookie_preview = session.cookies['JSESSIONID'][:10]
        logger.info(f"Success: Captured JSESSIONID ({cookie_preview}...)")
        return True
        
    logger.error("Failed to capture JSESSIONID.")
    return False


def extract_csrf_token(html_content: str) -> Optional[str]:
    """
    Parses HTML to find the hidden CSRF security token required for POST requests.
    Separated from network requests to allow for easy unit testing.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    csrf_input = soup.find('input', {'name': '_csrf'})
    
    if csrf_input and isinstance(csrf_input.get('value'), str):
        return csrf_input.get('value')
    return None


def prime_session_state(session: requests.Session) -> bool:
    """
    Navigates the Idox system to establish the server-side search state.
    This requires handling a CSRF token and mimicking a specific form submission.
    """
    logger.info("Priming server state (Handling CSRF & POST)...")
    search_page_url = f"{BASE_URL}search.do?action=advanced"
    
    # STEP 1: Land on the search page to grab the hidden CSRF token
    logger.debug("Fetching search page to find security token.")
    get_response = session.get(search_page_url)
    csrf_token = extract_csrf_token(get_response.text)
    
    if not csrf_token:
        logger.error("Could not find the _csrf token in the page HTML.")
        return False
        
    logger.debug(f"Found CSRF Token: {csrf_token}")
    
    # STEP 2: Submit the Form Data to initialize results
    primer_url = f"{BASE_URL}currentListResults.do?action=firstPage"
    payload = {
        "_csrf": csrf_token,
        "currentListSearch": "true",
        "searchCriteria.currentListSearch": "true",
        "searchType": "Application"
    }
    
    # Pretend we submitted this directly from the search page to avoid triggering security blocks
    session.headers.update({'Referer': search_page_url})
    post_response = session.post(primer_url, data=payload)
    
    # STEP 3: Verify the state was primed successfully
    if "session has timed out" in post_response.text.lower():
         logger.error("The server explicitly timed us out on the POST request.")
         return False
         
    # Quick check if the server handed us an explicit error page
    soup = BeautifulSoup(post_response.text, 'html.parser')
    if soup.title and "error" in soup.title.string.lower():
         logger.error("The server returned an error page during priming.")
         return False
         
    logger.info("Server state primed successfully.")
    return True


# ----------------------------------------------
# Application Data Extraction Logic
# ----------------------------------------------

def extract_application_id_from_app_html(app_html) -> str:
    """
    Given a single application HTML element, extract the application ID (Ref. No).
    This is a helper function to keep the main extraction logic clean.
    """
    app_id = "N/A"
    
    meta_tag = app_html.find('p', class_='metaInfo')
    if meta_tag:
        meta_parts = meta_tag.text.split('|')
        for part in meta_parts:
            clean_part = " ".join(part.split())
            if clean_part.startswith("Ref. No:"):
                app_id = clean_part.replace("Ref. No:", "").strip()
                break

    return app_id

def extract_application_url_from_app_html(app_html) -> str:
    """
    Given a single application HTML element, extract the application URL.
    This is a helper function to keep the main extraction logic clean.
    """
    app_url = "N/A"
    
    link_tag = app_html.find('a')
    if link_tag and link_tag.get('href'):
        app_url = urljoin(BASE_URL, link_tag.get('href'))

    return app_url

def extract_id_and_url_from_application_result(app_html) -> Dict[str, str]:
    """
    Given a single application HTML element, extract the application ID and URL.
    This is a helper function to keep the main extraction logic clean.
    """
    app_id = extract_application_id_from_app_html(app_html)
    app_url = extract_application_url_from_app_html(app_html)

    return {
        "application_id": app_id,
        "url": app_url
    }

def extract_application_results_from_results_page(html_content: str) -> List[Dict[str, str]]:
    """
    Parses the HTML for a results page, and for each application found, extracts the application ID and URL.
    Returns a list of dictionaries containing the extracted data for each application.
    """
    page_data: List[Dict[str, str]] = []
    soup = BeautifulSoup(html_content, 'html.parser')
    apps = soup.find_all('li', class_='searchresult')

    logger.info(f"Found {len(apps)} search result elements on page")
    
    for app in apps:
        extracted_data = extract_id_and_url_from_application_result(app)
        page_data.append(extracted_data)
        logger.debug(f"Extracted: {extracted_data['application_id']} - {extracted_data['url']}")
        
    return page_data


def get_current_applications(session) -> List[Dict[str, str]]:
    """
    Main function to run the scraper and extract all current applications.
    Scrapes all available pages until no more results are found or a session timeout occurs.
    """
    
    if not acquire_session_cookie(session):
        logger.error("Failed to acquire session cookie. Exiting.")
        return []
        
    if not prime_session_state(session):
        logger.error("Failed to prime session state. Exiting.")
        return []
    
    applications: List[Dict[str, str]] = []
    page = 1

    while True:
        if page == 2:
            logger.info("Reached page 5, stopping pagination to avoid potential issues.")
            break

        logger.info(f"Fetching Page {page}...")
        url = f"{BASE_URL}pagedSearchResults.do?action=page&searchCriteria.page={page}"
        response = session.get(url)

        if "session has timed out" in response.text.lower():
            logger.warning(f"Session timed out on page {page}. Attempting to re-prime session state.")
            if not prime_session_state(session):
                logger.error("Failed to re-prime session state. Stopping pagination.")
                break
            continue  # Retry the same page after re-priming

        extracted_apps = extract_application_results_from_results_page(response.text)
        
        if not extracted_apps:
            logger.info(f"No applications found on page {page}. Ending pagination.")
            break
            
        applications.extend(extracted_apps)
        page += 1

    return applications


def extract_application_details_from_summary_page(html_content: str) -> Dict[str, any]: # Change name to parse application summary later
    """
    Parses the HTML of an application's summary page to extract the required details.
    This function takes the raw HTML content of the summary page and returns a dictionary with the extracted fields.
    The returned dictionary will have the following structure:
    {
        "address": str,
        "description": str,
        "status": str,
        "validation_date": str
    }
    """
    # Returns placeholder data for now - the actual parsing logic will be implemented in the next phase when we have the real HTML structure to work with.
    return {
        "address": "123 Example Street SE1 2AB",
        "description": "Description of the application.",
        "status": "Validated",
        "validation_date": "2024-01-01"
    }

def extract_pdfs_from_documents_page(html_content: str) -> List[Dict[str, str]]:
    """
    Parses the HTML of an application's documents page to extract any associated PDFs.
    This function takes the raw HTML content of the documents page and returns a list of dictionaries, 
    each containing the PDF URL and its document type.
    """
    pdf_documents: List[Dict[str, str]] = []
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Locate the main documents table
    documents_table = soup.find('table', id='Documents')
    
    if not documents_table:
        logger.debug("No documents table found on this page.")
        return pdf_documents
        
    # Iterate through each row, skipping the table header (<th>) rows automatically 
    # since we explicitly look for table data (<td>) cells.
    rows = documents_table.find_all('tr')
    
    for row in rows:
        cols = row.find_all('td')
        
        # Ensure the row has the expected number of columns to avoid index errors
        # Columns: [0] Checkbox, [1] Date, [2] Type, [3] Drawing No, [4] Description, [5] View Link
        if len(cols) >= 6:
            document_type = cols[2].get_text(strip=True)
            
            # The PDF download/view link is located in an anchor tag in the final column
            view_link_tag = cols[5].find('a')
            
            if view_link_tag and view_link_tag.get('href'):
                raw_url = view_link_tag.get('href')
                
                # Convert the relative href into a fully qualified URL using the global BASE_URL
                pdf_url = urljoin(BASE_URL, raw_url)
                
                pdf_documents.append({
                    "pdf_url": pdf_url,
                    "document_type": document_type
                })
                
    logger.debug(f"Successfully extracted {len(pdf_documents)} PDFs.")
    return pdf_documents

def scrape_data_at_application_page(session: requests.Session, application: Dict[str, str]) -> Optional[Dict[str, any]]:
    """
    Navigates to a single application's details page and scrapes the required data fields.
    This function takes a single application dictionary with its URL, visits the URL, and extracts the desired data fields, returning a dictionary with the complete data for that application.
    """
    app_id = application.get('application_id', 'Unknown ID')
    logger.info(f"Enriching data for application: {app_id}")

    try:
        # Generate target URLs for this specific application
        document_url = get_documents_url_for_application(application)
        summary_url = get_summary_url_for_application(application)

        # Scrape the summary page for the main application details
        logger.debug(f"[{app_id}] Fetching summary page...")
        summary_response = session.get(summary_url)
        summary_response.raise_for_status() # Raise an exception for bad HTTP status codes
        summary_data = extract_application_details_from_summary_page(summary_response.text)
        logger.debug(f"[{app_id}] Successfully parsed summary details.")

        # Scrape the documents page for any associated PDFs
        logger.debug(f"[{app_id}] Fetching documents page...")
        document_response = session.get(document_url)
        document_response.raise_for_status()
        pdf_data = extract_pdfs_from_documents_page(document_response.text)
        logger.debug(f"[{app_id}] Extracted {len(pdf_data)} PDFs.")

        # Combine the summary data and PDF data into a single dictionary
        enriched_app = {
            "application_number": app_id,
            "source_url": application.get('url', ''),
            "address": summary_data.get("address", ""),
            "postcode": "",  # Placeholder: Implement extraction in summary parser later
            "description": summary_data.get("description", ""),
            "status": summary_data.get("status", ""),
            "validation_date": summary_data.get("validation_date", ""),
            "pdfs": pdf_data
        }
        
        logger.info(f"Successfully enriched application: {app_id}")
        return enriched_app

    except requests.exceptions.RequestException as e:
        logger.error(f"[{app_id}] Network error while scraping application: {e}")
        return None
    except Exception as e:
        logger.error(f"[{app_id}] Unexpected error while scraping application: {e}")
        return None


def scrape_data_at_application_pages(session: requests.Session, applications: List[Dict[str, str]]) -> List[Dict[str, any]]:
    """
    For each application in the list, scrapes the data from its details page and enriches the application data with the extracted fields.
    """
    enriched_applications = []
    total_apps = len(applications)
    
    logger.info(f"Starting detailed scrape for {total_apps} applications...")

    for index, app in enumerate(applications, start=1):
        logger.debug(f"Processing {index}/{total_apps}...")
        
        enriched_data = scrape_data_at_application_page(session, app)
        
        # Only append if the scrape was successful (didn't return None due to an error)
        if enriched_data:
            enriched_applications.append(enriched_data)

    logger.info(f"Enrichment complete. Successfully processed {len(enriched_applications)} out of {total_apps} applications.")
    return enriched_applications
   

# ----------------------------------------------
# Main Orchestrator
# ----------------------------------------------

def filter_new_applications(scraped_apps: List[Dict[str, str]], existing_app_ids: List[str]) -> List[Dict[str, str]]:
    """
    Compares the scraped applications against existing application IDs from the database,
    and returns only those applications that are new and need to be added.
    """
    new_apps = [app for app in scraped_apps if app['application_id'] not in existing_app_ids]
    logger.info(f"Filtered {len(new_apps)} new applications to add to the database.")
    return new_apps


def get_application_ids_from_database(conn) -> List[str]:
    """ Gets a list of application IDs that are already in the database to avoid duplicates. """
    if conn is None:
        return []
    
    with conn.cursor() as cursor:
        cursor.execute("SELECT application_id FROM applications")
        existing_ids = [row[0] for row in cursor.fetchall()]

    return existing_ids


def run_scraper() -> List[Dict[str, str]]:
    """
    The main orchestrator function that sets up the session, authenticates, 
    and paginates through the search results.
    
    """
    # Creates the session to use for all requests, which will handle cookies and headers
    session = create_scraper_session()
    
    # Gets the current applications by navigating through the search results pages
    current_applications = get_current_applications(session)

    print(f"Total applications scraped: {len(current_applications)}")

    existing_app_ids = get_application_ids_from_database(conn=None)  
    filtered_applications = filter_new_applications(current_applications, existing_app_ids)

    print(f"New applications to enrich: {len(filtered_applications)}")

    applications_enriched = scrape_data_at_application_pages(session, filtered_applications)  

    # Scrapes the details for each application that needs adding
    return applications_enriched


if __name__ == "__main__":
    logger.info("Starting Tower Hamlets Scraper...")
    results = run_scraper()
    example_results = results[:5]  # Show a sample of the results
    logger.info(f"Sample Extracted Applications: {example_results}")
    logger.info(f"Scrape Complete! Total applications found: {len(results)}")