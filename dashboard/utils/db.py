"""Database connection helper.

In production (ECS), credentials are fetched from AWS Secrets Manager.
Set the SECRET_NAME environment variable to the secret's name/ARN.

For local development, falls back to individual DB_* env vars loaded
from a .env file.
"""

import json
import logging
import os

import boto3
import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

SECRET_NAME = os.getenv("SECRET_NAME", "c22-planning-pipeline-db-credentials")
AWS_REGION = os.getenv("AWS_REGION", "eu-west-2")


def _get_credentials() -> dict:
    """Return DB credentials, preferring Secrets Manager over .env.

    On ECS the task role provides access to Secrets Manager automatically.
    Locally, if AWS credentials aren't configured or the secret can't be
    reached, we fall back to the DB_* environment variables from .env.
    """
    try:
        client = boto3.client("secretsmanager", region_name=AWS_REGION)
        response = client.get_secret_value(SecretId=SECRET_NAME)
        secret = json.loads(response["SecretString"])
        logging.info("Loaded credentials from Secrets Manager.")
        return {
            "host": secret["host"],
            "port": secret.get("port", 5432),
            "dbname": secret["dbname"],
            "user": secret["username"],
            "password": secret["password"],
        }
    except Exception as exc:
        logging.info(
            "Secrets Manager unavailable (%s), falling back to .env.", exc)
        return {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT", 5432),
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }


@st.cache_resource
def get_connection():
    """Return a long-lived connection to the Postgres database."""
    creds = _get_credentials()
    ssl_cert = os.getenv("DB_SSL_CERT", "./global-bundle.pem")

    try:
        conn = psycopg2.connect(
            host=creds["host"],
            port=creds["port"],
            dbname=creds["dbname"],
            user=creds["user"],
            password=creds["password"],
            sslmode="verify-full",
            sslrootcert=ssl_cert,
        )
        logging.info("Successfully connected to database.")
        return conn
    except psycopg2.OperationalError as e:
        st.error(f"Database connection failed: {e}")
        raise
