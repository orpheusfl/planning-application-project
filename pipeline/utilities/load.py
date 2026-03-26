""" This module contains functions to load application data into the RDS. """

# ------------------------------------------------------------
# Imports
# ------------------------------------------------------------

import logging
import os
import psycopg2
from dotenv import load_dotenv

# ------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ------------------------------------------------------------
# Get rds connection
# ------------------------------------------------------------


def get_rds_connection(rds_host: str, rds_port: int, rds_user: str,
                       rds_password: str, rds_db_name: str):
    """ Establishes a connection to the RDS database. """
    try:
        conn = psycopg2.connect(
            host=rds_host,
            port=rds_port,
            user=rds_user,
            password=rds_password,
            dbname=rds_db_name
        )
        logging.info("Successfully connected to RDS database.")
        return conn
    except Exception as e:
        logging.error("Error connecting to RDS database: %s", e)
        raise

# ------------------------------------------------------------
# Load application data to the RDS
# ------------------------------------------------------------


def get_council_id(conn, council_name: str, council_table_name: str) -> int:
    """ Retrieves the council_id from councils table based on council_name. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT council_id FROM {council_table_name} "
                f"WHERE council_name ILIKE %s", (council_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            logging.error("Council name '%s' not found in database.",
                          council_name)
            raise ValueError(
                f"Council name '{council_name}' not found in database.")
    except ValueError:
        raise
    except Exception as e:
        logging.error("Error retrieving council_id: %s", e)
        raise


def get_status_type_id(conn, status_name: str,
                       status_type_table_name: str) -> int:
    """ Retrieves status_type_id from status_types table. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT status_type_id FROM {status_type_table_name} "
                f"WHERE status_type ILIKE %s", (status_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            logging.error("Status type '%s' not found in database.",
                          status_name)
            raise ValueError(
                f"Status type '{status_name}' not found in database.")
    except ValueError:
        raise
    except Exception as e:
        logging.error("Error retrieving status_type_id: %s", e)
        raise


def get_application_type_id(conn, application_type_name: str,
                            application_type_table_name: str) -> int:
    """ Retrieves application_type_id from application_types table. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT application_type_id FROM {application_type_table_name} "
                f"WHERE application_type ILIKE %s", (application_type_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            logging.error("Application type '%s' not found in database.",
                          application_type_name)
            raise ValueError(
                f"Application type '{application_type_name}' "
                "not found in database.")
    except ValueError:
        raise
    except Exception as e:
        logging.error("Error retrieving application_type_id: %s", e)
        raise


def load_application_to_rds(conn, table_name: str, application_data: dict,
                            council_id: int, status_type_id: int,
                            application_type_id: int) -> int:
    """ Inserts application data and returns generated application_id.
        The application_data dictionary should contain:
        - application_number, validation_date, address, postcode, lat, long,
          ai_summary, source_url, public_interest_score
    """
    try:
        with conn.cursor() as cursor:
            insert_query = f"""
                INSERT INTO {table_name} (
                    application_number, validation_date, address, postcode,
                    lat, long, ai_summary, public_interest_score,
                    council_id, status_type_id, application_type_id,
                    application_page_url, document_page_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING application_id
            """
            cursor.execute(insert_query, (
                application_data['application_number'],
                application_data['validation_date'],
                application_data['address'],
                application_data['postcode'],
                application_data['lat'],
                application_data['long'],
                application_data['ai_summary'],
                application_data['public_interest_score'],
                council_id,
                status_type_id,
                application_type_id,
                application_data['application_page_url'],
                application_data['document_page_url']
            ))
            application_id = cursor.fetchone()[0]
            conn.commit()
            logging.info(
                "Successfully inserted application data with id: %s",
                application_id)
            return application_id
    except Exception as e:
        logging.error("Error inserting application data into RDS: %s", e)
        conn.rollback()
        raise


# ------------------------------------------------------------
# Load application data to the RDS
# ------------------------------------------------------------


def validate_environment_variables():
    """ Validates that all required environment variables are set. """
    required_env_vars = [
        'APPLICATION_FACT_TABLE',
        'COUNCIL_DIM_TABLE',
        'STATUS_DIM_TABLE',
        'APPLICATION_TYPE_DIM_TABLE',

    ]

    missing_env_vars = [var for var in required_env_vars
                        if not os.getenv(var)]
    if missing_env_vars:
        error_msg = f"Missing required environment variables: \
            {', '.join(missing_env_vars)}"
        logging.error("Missing required environment variables: %s",
                      ', '.join(missing_env_vars))
        raise ValueError(error_msg)


def load_application_data(conn, council_name: str,
                          application_info: dict):
    """ Loads application data to database.
        The application_info dict should contain:
        - application_number, validation_date, address, postcode, lat, long,
          ai_summary, public_interest_score, status_type, application_type,
          application_page_url, document_page_url, documents (list of dicts with file_path, document_type)
        This function will validate the environment variables, retrieve necessary foreign key ids,
        and then load the application data to the RDS.
    """
    validate_environment_variables()

    # Gets the necessary foreign key ids for the application record from the RDS

    council_id = get_council_id(
        conn, council_name, os.getenv('COUNCIL_DIM_TABLE'))

    status_type_id = get_status_type_id(
        conn, application_info['status_type'],
        os.getenv('STATUS_DIM_TABLE'))

    application_type_id = get_application_type_id(
        conn, application_info['application_type'],
        os.getenv('APPLICATION_TYPE_DIM_TABLE'))

    load_application_to_rds(
        conn, os.getenv('APPLICATION_FACT_TABLE'), application_info,
        council_id, status_type_id, application_type_id)


if __name__ == "__main__":
    logging.info(
        "This module is intended to be imported and used by other modules, not run directly.")

    load_dotenv()  # Load environment variables from .env file

    # Tests that the functions can store some dummy data
    try:
        # Example usage with dummy data
        conn = get_rds_connection(
            rds_host='c22-planning-pipeline-db.c57vkec7dkkx.eu-west-2.rds.amazonaws.com',
            rds_port=5432,
            rds_user='',
            rds_password='',
            rds_db_name='planning_db'
        )

        # Tests that the connection can be established and a simple query can be run
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            logging.info("Test query result: %s", result)

        # Test that application data can be loaded (using dummy data)
        dummy_application_info = {
            'application_number': 'PA/99/99999',
            'validation_date': '2024-01-01',
            'address': '123 Test Street',
            'postcode': 'TE5 7ST',
            'lat': 51.5074,
            'long': -0.1278,
            'ai_summary': 'This is a test summary.',
            'public_interest_score': 5,
            'status_type': 'Registered',
            'application_type': 'Full Planning Permission',
            'application_page_url': 'https://example.com/app?id=PA/99/99999',
            'document_page_url': 'https://example.com/app?id=PA/99/99999&activeTab=documents'
        }

        load_application_data(conn, 'Tower Hamlets', dummy_application_info)
    except Exception as e:
        logging.error("Error during test connection: %s", e)
