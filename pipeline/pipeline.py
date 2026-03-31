"""Full ETL pipeline for the project.

1. Extracts data from websites
2. Transforms data into a clean format and calls the LLM to generate insights
3. Loads the insights into a RDS database
"""

import logging
import os

from dotenv import load_dotenv

from utilities.extract import run_scraper_current_applications, run_scraper_weekly_applications
from utilities.transform import Application
from utilities.load import get_rds_connection, load_application_data, update_application_data

logger = logging.getLogger(__name__)

COUNCIL_NAME = "Tower Hamlets"
MAX_APPLICATIONS_PER_RUN = 10


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


def deduplicate_applications(applications: list[dict]) -> list[dict]:
    """Remove duplicate applications by application_number, keeping the last occurrence.

    Later entries are preferred because the weekly decided scraper runs second
    and provides decision data that the current scraper may lack.
    """
    seen: dict[str, dict] = {}
    for app in applications:
        app_id = app.get('application_number')
        if app_id in seen:
            logger.info(
                "Duplicate found: %s — keeping weekly-scraper version", app_id)
        seen[app_id] = app
    return list(seen.values())


def extract_all_applications(conn) -> list[dict]:
    """Run both scrapers and return a deduplicated list of raw application stubs."""
    current = run_scraper_current_applications(conn)
    logger.info("Extracted %d current applications.", len(current))

    weekly_decided = run_scraper_weekly_applications(conn)
    logger.info("Extracted %d weekly decided applications.",
                len(weekly_decided))

    combined = current + weekly_decided
    deduplicated = deduplicate_applications(combined)

    if len(combined) != len(deduplicated):
        logger.info("Deduplicated %d → %d applications.",
                    len(combined), len(deduplicated))

    return deduplicated


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


def process_applications(conn, raw_applications: list[dict], api_key: str) -> list[dict]:
    """Process each raw application up to the per-run limit.

    Returns a list of successfully processed application dicts.
    """
    processed = []
    skipped = []

    for raw_app in raw_applications:
        result = process_application(conn, raw_app, api_key)

        if result is not None:
            processed.append(result)
        else:
            app_id = raw_app.get('application_number', 'Unknown')
            skipped.append(app_id)

        if len(processed) >= MAX_APPLICATIONS_PER_RUN:
            logger.info("Reached the per-run limit of %d applications.",
                        MAX_APPLICATIONS_PER_RUN)
            break

    if skipped:
        logger.warning("Skipped %d applications: %s",
                       len(skipped), ", ".join(skipped))

    logger.info("Processing complete: %d processed, %d skipped",
                len(processed), len(skipped))
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

    # Scrapes for all applications data
    raw_applications = extract_all_applications(conn)

    # Processes each application and loads insights into the database
    processed = process_applications(conn, raw_applications, api_key)

    logger.info("Pipeline complete. Processed %d applications.", len(processed))


if __name__ == "__main__":
    main()
