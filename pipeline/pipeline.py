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
    conn = get_rds_connection(
        DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
    print(run_scraper(conn))


if __name__ == "__main__":
    main()
