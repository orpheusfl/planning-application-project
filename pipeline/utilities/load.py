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
# Get s3 client
# ------------------------------------------------------------


def get_s3_client(aws_access_key_id: str, aws_secret_access_key: str,
                  aws_region: str):
    """ Creates an S3 client using the provided AWS credentials. """
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
        logging.info("Successfully created S3 client.")
        return s3_client
    except Exception as e:
        logging.error("Error creating S3 client: %s", e)
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
                "Successfully inserted application data with id: %s",
                application_id)
            return application_id
    except Exception as e:
        logging.error("Error inserting application data into RDS: %s", e)
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
            "Successfully uploaded %s to S3 bucket %s with key %s",
            file_path, bucket_name, s3_key)
    except Exception as e:
        logging.error("Error uploading file to S3: %s", e)
        raise


def load_list_of_pdfs_to_s3(s3_client, bucket_name: str, file_paths: list,
                            council_name: str, application_number: str):
    """ Uploads a list of PDF files to the specified S3 bucket. 
    Takes a list of local file paths and S3 key prefix as input. """
    try:
        for file_path in file_paths:
            s3_key = generate_s3_key(
                council_name, application_number, os.path.basename(file_path))
            load_pdf_to_s3(s3_client, bucket_name, file_path, s3_key)
    except Exception as e:
        logging.error("Error uploading files to S3: %s", e)
        raise


def generate_s3_key(council_name: str, application_number: str, file_name: str):
    """ Generates a unique S3 key for the uploaded file. """
    s3_key = f"application_documents/{council_name}/{application_number}/{file_name}"
    return s3_key

# ------------------------------------------------------------
# Load application document metadata to the RDS
# ------------------------------------------------------------


def get_document_type_id(conn, document_type_name: str,
                         document_type_table_name: str) -> int:
    """ Retrieves document_type_id from document_types table. """
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT document_type_id FROM {document_type_table_name} "
                f"WHERE document_type ILIKE %s", (document_type_name,))
            result = cursor.fetchone()
            if result:
                return result[0]
            logging.error("Document type '%s' not found in database.",
                          document_type_name)
            raise ValueError(
                f"Document type '{document_type_name}' not found in database.")
    except ValueError:
        raise
    except Exception as e:
        logging.error("Error retrieving document_type_id: %s", e)
        raise


def load_document_metadata_to_rds(conn, table_name: str, application_id: int,
                                  s3_object_key: str, document_type_id: int):
    """ Inserts document metadata into application_documents table. """
    try:
        with conn.cursor() as cursor:
            insert_query = f"""
                INSERT INTO {table_name} (
                    application_id, document_type_id, s3_object_key
                ) VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (
                application_id,
                document_type_id,
                s3_object_key
            ))
            conn.commit()
            logging.info(
                "Successfully inserted document metadata for application_id: %s",
                application_id)
    except Exception as e:
        logging.error("Error inserting document metadata into RDS: %s", e)
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
    missing_env_vars = [var for var in required_env_vars
                        if not os.getenv(var)]
    if missing_env_vars:
        error_msg = f"Missing required environment variables: \
            {', '.join(missing_env_vars)}"
        logging.error("Missing required environment variables: %s",
                      ', '.join(missing_env_vars))
        raise ValueError(error_msg)


def load_application_data_and_pdfs(conn, council_name: str,
                                   application_info: dict, s3_client,
                                   bucket_name: str):
    """ Loads application data and supporting documents to database.
        The application_info dict should contain:
        - application_number, validation_date, address, postcode, lat, long,
          ai_summary, public_interest_score, status_type, application_type,
          source_url, documents (list of dicts with file_path, document_type)
    """
    validate_environment_variables()

    council_id = get_council_id(
        conn, council_name, os.getenv('COUNCIL_TABLE_NAME'))
    status_type_id = get_status_type_id(
        conn, application_info['status_type'],
        os.getenv('STATUS_TYPE_TABLE_NAME'))
    application_type_id = get_application_type_id(
        conn, application_info['application_type'],
        os.getenv('APPLICATION_TYPE_TABLE_NAME'))

    application_id = load_application_to_rds(
        conn, os.getenv('APPLICATION_TABLE_NAME'), application_info,
        council_id, status_type_id, application_type_id)

    for document in application_info['documents']:
        file_name = os.path.basename(document['file_path'])
        s3_key = generate_s3_key(
            council_name, application_info['application_number'], file_name)
        load_pdf_to_s3(s3_client, bucket_name, document['file_path'], s3_key)
        document_type_id = get_document_type_id(
            conn, document['document_type'],
            os.getenv('DOCUMENT_TYPE_TABLE_NAME'))
        load_document_metadata_to_rds(
            conn, os.getenv('DOCUMENT_TABLE_NAME'), application_id,
            s3_key, document_type_id)
