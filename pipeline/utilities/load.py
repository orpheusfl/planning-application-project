""" This module contains functions to load application data into the RDS and s3 buckets. """

# ------------------------------------------------------------
# Imports
# ------------------------------------------------------------

import logging
import os
import psycopg2
import boto3

# ------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# ------------------------------------------------------------
# Get rds connection
# ------------------------------------------------------------


def get_rds_connection(RDS_HOST: str, RDS_PORT: int, RDS_USER: str, RDS_PASSWORD: str, RDS_DB_NAME: str):
    """ Establishes a connection to the RDS database. """
    try:
        conn = psycopg2.connect(
            host=RDS_HOST,
            port=RDS_PORT,
            user=RDS_USER,
            password=RDS_PASSWORD,
            dbname=RDS_DB_NAME
        )
        logging.info("Successfully connected to RDS database.")
        return conn
    except Exception as e:
        logging.error(f"Error connecting to RDS database: {e}")
        raise


# ------------------------------------------------------------
# Get s3 client
# ------------------------------------------------------------


def get_s3_client(AWS_ACCESS_KEY_ID: str, AWS_SECRET_ACCESS_KEY: str, AWS_REGION: str):
    """ Creates an S3 client using the provided AWS credentials. """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
        logging.info("Successfully created S3 client.")
        return s3_client
    except Exception as e:
        logging.error(f"Error creating S3 client: {e}")
        raise


# ------------------------------------------------------------
# Load application data to the RDS
# ------------------------------------------------------------

def get_council_id(conn, council_name: str, council_table_name: str) -> int:
    """ Retrieves the council_id from the councils table based on the council_name. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT council_id FROM {council_table_name} WHERE council_name ILIKE %s", (council_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                logging.error(
                    f"Council name '{council_name}' not found in the database.")
                raise ValueError(
                    f"Council name '{council_name}' not found in the database.")
    except Exception as e:
        logging.error(f"Error retrieving council_id: {e}")
        raise


def get_status_type_id(conn, status_name: str, status_type_table_name: str) -> int:
    """ Retrieves the status_type_id from the status_types table based on the status_type. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT status_type_id FROM {status_type_table_name} WHERE status_type ILIKE %s", (status_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                logging.error(
                    f"Status type '{status_name}' not found in the database.")
                raise ValueError(
                    f"Status type '{status_name}' not found in the database.")
    except Exception as e:
        logging.error(f"Error retrieving status_type_id: {e}")
        raise


def get_application_type_id(conn, application_type_name: str, application_type_table_name: str) -> int:
    """ Retrieves the application_type_id from the application_types table based on the application_type. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT application_type_id FROM {application_type_table_name} WHERE application_type ILIKE %s", (application_type_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                logging.error(
                    f"Application type '{application_type_name}' not found in the database.")
                raise ValueError(
                    f"Application type '{application_type_name}' not found in the database.")
    except Exception as e:
        logging.error(f"Error retrieving application_type_id: {e}")
        raise


def load_application_to_rds(conn, table_name: str, application_data: dict, council_id: int, status_type_id: int, application_type_id: int) -> int:
    """ Inserts application data into the applications table and returns the generated application_id.
        The application_data dictionary should contain the following keys:
        - application_number
        - validation_date
        - address
        - postcode
        - lat
        - long
        - ai_summary
        - source_url
        - public_interest_score
    """
    try:
        with conn.cursor() as cursor:
            insert_query = f"""
                INSERT INTO {table_name} (
                    application_number, 
                    validation_date, 
                    address, 
                    postcode, 
                    lat, 
                    long, 
                    ai_summary, 
                    public_interest_score, 
                    council_id, 
                    status_type_id, 
                    application_type_id,
                    source_url
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
                application_data['source_url']
            ))
            application_id = cursor.fetchone()[0]
            conn.commit()
            logging.info(
                f"Successfully inserted application data into RDS with application_id: {application_id}.")
            return application_id
    except Exception as e:
        logging.error(f"Error inserting application data into RDS: {e}")
        conn.rollback()
        raise

# ------------------------------------------------------------
# Load pdf to s3
# ------------------------------------------------------------


def load_pdf_to_s3(s3_client, bucket_name: str, file_path: str, s3_key: str):
    """ Uploads a PDF file to the specified S3 bucket. 
    Takes the local file path and the desired S3 key as input. """
    try:
        s3_client.upload_file(file_path, bucket_name, s3_key)
        logging.info(
            f"Successfully uploaded {file_path} to S3 bucket {bucket_name} with key {s3_key}.")
    except Exception as e:
        logging.error(f"Error uploading file to S3: {e}")
        raise


def load_list_of_pdfs_to_s3(s3_client, bucket_name: str, file_paths: list, council_name: str, application_number: str):
    """ Uploads a list of PDF files to the specified S3 bucket. 
    Takes a list of local file paths and the desired S3 key prefix as input. """
    try:
        for file_path in file_paths:
            s3_key = generate_s3_key(
                council_name, application_number, os.path.basename(file_path))
            load_pdf_to_s3(s3_client, bucket_name, file_path, s3_key)
    except Exception as e:
        logging.error(f"Error uploading files to S3: {e}")
        raise


def generate_s3_key(council_name: str, application_number: str, file_name: str):
    """ Generates a unique S3 key for the uploaded file. """
    s3_key = f"application_documents/{council_name}/{application_number}/{file_name}"
    return s3_key

# ------------------------------------------------------------
# Load application document metadata to the RDS
# ------------------------------------------------------------


def get_document_type_id(conn, document_type_name: str, document_type_table_name: str) -> int:
    """ Retrieves the document_type_id from the document_types table based on the document_type. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT document_type_id FROM {document_type_table_name} WHERE document_type ILIKE %s", (document_type_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                logging.error(
                    f"Document type '{document_type_name}' not found in the database.")
                raise ValueError(
                    f"Document type '{document_type_name}' not found in the database.")
    except Exception as e:
        logging.error(f"Error retrieving document_type_id: {e}")
        raise


def load_document_metadata_to_rds(conn, table_name: str, application_id: int, s3_object_key: str, document_type_id: int):
    """ Inserts document metadata into the application_documents table.
        The document_data dictionary should contain the following keys:
        - s3_object_key
        - file_name
    """
    try:
        with conn.cursor() as cursor:
            insert_query = f"""
                INSERT INTO {table_name} (
                    application_id, 
                    document_type_id, 
                    s3_object_key
                ) VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (
                application_id,
                document_type_id,
                s3_object_key
            ))
            conn.commit()
            logging.info(
                f"Successfully inserted document metadata into RDS for application_id: {application_id}.")
    except Exception as e:
        logging.error(f"Error inserting document metadata into RDS: {e}")
        conn.rollback()
        raise

# ------------------------------------------------------------
# Load application data to the RDS and pdf to s3
# ------------------------------------------------------------


def validate_environment_variables():
    """ Validates that all required environment variables are set. """
    required_env_vars = [
        'APPLICATION_TABLE_NAME',
        'DOCUMENT_TABLE_NAME',
        'COUNCIL_TABLE_NAME',
        'STATUS_TYPE_TABLE_NAME',
        'APPLICATION_TYPE_TABLE_NAME',
        'DOCUMENT_TYPE_TABLE_NAME'
    ]
    missing_env_vars = [var for var in required_env_vars if not os.getenv(var)]
    if missing_env_vars:
        logging.error(
            f"Missing required environment variables: {', '.join(missing_env_vars)}")
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing_env_vars)}")


def load_application_data_and_pdfs(conn, council_name: str, application_info: dict, s3_client, bucket_name: str):
    """ Loads all the data about an application to the database, including application information, and supporting documents.
        The application_info dictionary should contain the following keys:
            - application_number: str
            - validation_date: date
            - address: str
            - postcode: str
            - lat: float
            - long: float
            - ai_summary: str
            - public_interest_score: float
            - status_type: str
            - application_type: str
            - source_url: str
            - documents: list of dictionaries, where each dictionary should contain the following keys:
                - file_path: str (local file path to the PDF document)
                - document_type: str
            """

    # Validates that the environment variables are set
    validate_environment_variables()

    # Get council_id, status_type_id, and application_type_id
    council_id = get_council_id(
        conn, council_name, os.getenv('COUNCIL_TABLE_NAME'))
    status_type_id = get_status_type_id(
        conn, application_info['status_type'], os.getenv('STATUS_TYPE_TABLE_NAME'))
    application_type_id = get_application_type_id(
        conn, application_info['application_type'], os.getenv('APPLICATION_TYPE_TABLE_NAME'))

    # Load application data to RDS
    application_id = load_application_to_rds(conn, os.getenv(
        'APPLICATION_TABLE_NAME'), application_info, council_id, status_type_id, application_type_id)

    # Load PDFs to S3 and document metadata to RDS
    for document in application_info['documents']:
        s3_key = generate_s3_key(
            council_name, application_info['application_number'], os.path.basename(document['file_path']))
        load_pdf_to_s3(s3_client, bucket_name, document['file_path'], s3_key)
        document_type_id = get_document_type_id(
            conn, document['document_type'], os.getenv('DOCUMENT_TYPE_TABLE_NAME'))
        load_document_metadata_to_rds(conn, os.getenv(
            'DOCUMENT_TABLE_NAME'), application_id, s3_key, document_type_id)
