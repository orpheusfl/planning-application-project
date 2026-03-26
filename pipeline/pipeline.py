"""Full ETL pipeline for the project. 
    1. Extracts data from websites
    2. Transforms data into a clean format and calls the LLM to generate insights
    3. Loads the insights into a RDS database"""


from utilities.extract import run_scraper
from utilities.transform import Application
from utilities.load import get_rds_connection
from dotenv import load_dotenv
import os
import psycopg2
import logging

load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def main():
    conn = get_rds_connection(rds_host=DB_HOST, rds_port=DB_PORT, rds_user=DB_USER,
                              rds_password=DB_PASSWORD, rds_db_name=DB_NAME)
    raw_applications = run_scraper(conn)

    processed_applications = []

    for raw_app in raw_applications:
        app = Application(application_number=raw_app.get("application_number"),
                          application_type=raw_app.get("application_type"),
                          description=raw_app.get("description"),
                          address=raw_app.get("address"),
                          validation_date=raw_app.get("validation_date"),
                          status=raw_app.get("status"),
                          pdfs=raw_app.get("pdfs"),
                          application_url=raw_app.get("application_page_url"),
                          document_page_url=raw_app.get("document_page_url")
                          )
        app.process(API_KEY)
        processed_applications.append(app.to_dict())

        if len(processed_applications) > 3:
            break

    print(processed_applications)


if __name__ == "__main__":
    main()
