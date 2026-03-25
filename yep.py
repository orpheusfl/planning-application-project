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