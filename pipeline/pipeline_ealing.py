"""Full ETL pipeline for ealing planning applications.

1. Extracts data from websites
2. Transforms data into a clean format and calls the LLM to generate insights
3. Loads the insights into a RDS database
"""

import logging
import os

from dotenv import load_dotenv

from utilities.extract_ealing import run_scraper_weekly_applications
from utilities.transform import Application
from utilities.load import get_rds_connection, load_application_data, update_application_data

logger = logging.getLogger(__name__)

COUNCIL_NAME = "Ealing"
MAX_APPLICATIONS_PER_RUN = 100
CHUNK_SIZE = 50

# TEMPORARY: Blocker for testing PDF filtering with limited applications
TEST_MODE_ENABLED = True
TEST_APP_LIMIT_PER_DATE_TYPE = 10  # 10 validated + 10 decided


def build_db_connection(db_host: str, db_port: str, db_name: str,
                        db_user: str, db_password: str):
    """Establish and return a database connection."""
    return get_rds_connection(
        rds_host=db_host,
        rds_port=db_port,
        rds_user=db_user,
        rds_password=db_password,
        rds_db_name=db_name,
    )


def extract_all_applications(conn) -> list[dict]:
    """Run the weekly applications scraper and return raw application stubs."""
    app_limit = TEST_APP_LIMIT_PER_DATE_TYPE if TEST_MODE_ENABLED else None
    if app_limit:
        logger.warning(
            "TEST MODE ENABLED: Limiting to %d per date type (validated/decided)", app_limit)

    weekly_decided = run_scraper_weekly_applications(
        conn, app_limit=app_limit, enrich=False)
    logger.info("Extracted %d weekly decided application stubs.",
                len(weekly_decided))

    return weekly_decided


def build_application(raw_app: dict) -> Application:
    """Construct an Application object from a raw scraper stub."""
    urls = {
        'application_page_url': raw_app.get('application_page_url'),
        'document_page_url': raw_app.get('document_page_url'),
    }

    return Application(
        application_number=raw_app.get('application_number'),
        application_type=raw_app.get('application_type'),
        description=raw_app.get('description'),
        address=raw_app.get('address'),
        validation_date=raw_app.get('validation_date'),
        status=raw_app.get('status'),
        pdfs=raw_app.get('pdfs'),
        urls=urls,
        decision=raw_app.get('decision'),
        decision_date=raw_app.get('decision_date'),
        database_action=raw_app.get('database_action'),
    )


def handle_update(conn, app: Application) -> dict:
    """Update an existing application's status and decision fields in the database.

    Returns the serialised application dict.
    """
    app_dict = app.to_dict()
    update_application_data(
        conn, council_name=COUNCIL_NAME, application_info=app_dict)
    logger.info("Updated application %s.", app.application_number)
    return app_dict


def handle_insert(conn, app: Application, api_key: str) -> dict:
    """Enrich a new application via LLM and insert it into the database.

    Returns the enriched serialised application dict.
    """
    app.process(api_key)
    app_dict = app.to_dict()
    load_application_data(conn, council_name=COUNCIL_NAME,
                          application_info=app_dict)
    logger.info("Inserted application %s.", app.application_number)
    return app_dict


def process_application(conn, raw_app: dict, api_key: str) -> dict | None:
    """Dispatch a single raw application stub to the correct insert or update handler.

    Returns the processed application dict, or None if the action is unrecognised.
    """
    app = build_application(raw_app)
    database_action = raw_app.get('database_action')

    match database_action:
        case 'update':
            return handle_update(conn, app)
        case 'insert':
            return handle_insert(conn, app, api_key)
        case _:
            logger.warning(
                "Unrecognised database_action '%s' for application %s — skipping.",
                database_action,
                raw_app.get('application_number'),
            )
            return None


def process_applications_in_chunks(conn, raw_applications: list[dict], api_key: str) -> list[dict]:
    """Process applications in chunks of 50 to balance memory usage and LLM throughput.

    Loops through all applications, enriching and processing chunks sequentially.
    Each application is either inserted (new) or updated (existing) as determined by its database_action.

    Returns a list of successfully processed application dicts.
    """
    from utilities.extract_ealing import enrich_applications, create_scraper_session

    processed = []
    skipped = []
    total_to_process = len(raw_applications)

    logger.info("Processing %d applications in chunks of %d",
                total_to_process, CHUNK_SIZE)

    for i in range(0, len(raw_applications), CHUNK_SIZE):
        chunk = raw_applications[i:i + CHUNK_SIZE]
        chunk_num = (i // CHUNK_SIZE) + 1
        total_chunks = (len(raw_applications) + CHUNK_SIZE - 1) // CHUNK_SIZE

        logger.info("Processing chunk %d/%d (%d apps)",
                    chunk_num, total_chunks, len(chunk))

        # Enrich chunk
        session = create_scraper_session()
        enriched_chunk = enrich_applications(session, chunk)
        session.close()

        # Process each enriched application
        for enriched_app in enriched_chunk:
            result = process_application(conn, enriched_app, api_key)
            if result is not None:
                processed.append(result)
            else:
                skipped.append(enriched_app.get(
                    'application_number', 'unknown'))

            if len(processed) >= MAX_APPLICATIONS_PER_RUN:
                logger.info(
                    "Reached MAX_APPLICATIONS_PER_RUN limit (%d)", MAX_APPLICATIONS_PER_RUN)
                break

        if len(processed) >= MAX_APPLICATIONS_PER_RUN:
            break

    if skipped:
        logger.warning("Skipped %d applications: %s",
                       len(skipped), ", ".join(skipped))

    logger.info("Processing complete: %d processed, %d skipped out of %d total",
                len(processed), len(skipped), total_to_process)
    return processed


def main() -> None:
    """Orchestrate the full ETL pipeline: configure, connect, extract, and process."""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    if not all([api_key, db_host, db_port, db_name, db_user, db_password]):
        logger.error("One or more required environment variables are missing.")
        return

    conn = build_db_connection(db_host, db_port, db_name, db_user, db_password)

    # Extract all application stubs (quick extraction without detailed enrichment)
    raw_applications = extract_all_applications(conn)

    # Process applications in chunks of 50 (enriching and loading as we go)
    processed = process_applications_in_chunks(conn, raw_applications, api_key)

    logger.info("Pipeline complete. Processed %d applications.", len(processed))


if __name__ == "__main__":
    main()
