"""Database connection helper."""

import os

import psycopg2
import streamlit as st
from dotenv import load_dotenv

load_dotenv()


@st.cache_resource
def get_connection():
    """Return a long-lived connection to the Postgres database."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT", 5432),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        sslmode="verify-full",
        sslrootcert=os.getenv("DB_SSL_CERT", "./global-bundle.pem"),
    )
