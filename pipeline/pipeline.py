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
from utilities.load import get_rds_connection, load_application_data


def main():
    """Run the full ETL pipeline: extract, transform, and load planning applications."""

    # Load environment variables from .env file
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")

    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")

    # Validate that all necessary environment variables are set
    if not all([api_key, db_host, db_port, db_name, db_user, db_password]):
        logging.error(
            "One or more required environment variables are missing.")
        return

    # Connect to the RDS database
    conn = get_rds_connection(
        rds_host=db_host,
        rds_port=db_port,
        rds_user=db_user,
        rds_password=db_password,
        rds_db_name=db_name
    )

    current_applications = run_scraper_current_applications(conn)

    weekly_done_applications = run_scraper_weekly_applications(conn)

    all_applications_to_process = current_applications + weekly_done_applications

    processed_applications = []

    # For each of the extracted applications
    for raw_app in all_applications_to_process:

        # Extract the relevant URLs for the application
        urls = {
            'application_page_url': raw_app.get('application_page_url'),
            'document_page_url': raw_app.get('document_page_url')
        }

        # Transform the raw application data into a structured format and generate insights using the LLM
        app = Application(
            application_number=raw_app.get('application_number'),
            application_type=raw_app.get('application_type'),
            description=raw_app.get('description'),
            address=raw_app.get('address'),
            validation_date=raw_app.get('validation_date'),
            status=raw_app.get('status'),
            pdfs=raw_app.get('pdfs'),
            urls=urls,
            decision=raw_app.get('decision', None),
            decision_date=raw_app.get('decision_date', None),
            database_action=raw_app.get('database_action', None)
        )

        app.process(api_key)

        app_dict = app.to_dict()
        app_dict["decision"] = raw_app.get("decision")
        app_dict["decision_date"] = raw_app.get("decision_date")
        app_dict["database_action"] = raw_app.get("database_action")
        print(app_dict)

        processed_applications.append(app_dict)

        load_application_data(
            conn,
            council_name='Tower Hamlets',
            application_info=app.to_dict()
        )

        if len(processed_applications) > 50:
            break


if __name__ == "__main__":
    main()
