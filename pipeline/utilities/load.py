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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s') 

# ------------------------------------------------------------
# Get rds connection
# ------------------------------------------------------------
def get_rds_connection(RDS_HOST:str, RDS_PORT:int, RDS_USER:str, RDS_PASSWORD:str, RDS_DB_NAME:str):
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
def get_s3_client(AWS_ACCESS_KEY_ID:str, AWS_SECRET_ACCESS_KEY:str, AWS_REGION:str):
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
# Load pdf to s3
# ------------------------------------------------------------
def load_pdf_to_s3(s3_client, bucket_name:str, file_path:str, s3_key:str):
    """ Uploads a PDF file to the specified S3 bucket. """
    try:
        s3_client.upload_file(file_path, bucket_name, s3_key)
        logging.info(f"Successfully uploaded {file_path} to S3 bucket {bucket_name} with key {s3_key}.")
    except Exception as e:
        logging.error(f"Error uploading file to S3: {e}")
        raise

def generate_s3_key(council_name:str, application_number:str, file_name:str):
    """ Generates a unique S3 key for the uploaded file. """
    s3_key = f"application_documents/{council_name}/{application_number}/{file_name}"
    return s3_key

# ------------------------------------------------------------
# Load application data to the RDS 
# ------------------------------------------------------------
def load_data_to_rds(conn, table_name:str, data:list):
    """ Loads data into the specified RDS table. 
    data should be a list of dictionaries, where each dictionary represents a row to be inserted into the table. 
    The keys of the dictionary should correspond to the column names in the table.
    """
    try:
        with conn.cursor() as cursor:
            for row in data:
                placeholders = ', '.join(['%s'] * len(row))
                columns = ', '.join(row.keys())
                sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
                cursor.execute(sql, list(row.values()))
            conn.commit()
        logging.info(f"Successfully loaded data into RDS table {table_name}.")
    except Exception as e:
        logging.error(f"Error loading data into RDS table {table_name}: {e}")
        conn.rollback()
        raise