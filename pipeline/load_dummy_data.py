"""
One-off script to load dummy planning application data into the live RDS.

Reads from dashboard/dummy_data.py, maps columns to the schema expected by
pipeline/utilities/load.py, then inserts all 15 applications and 23 documents.

S3 uploads are skipped (no real PDFs) — the s3_uri from dummy data is stored
directly as the s3_object_key in the document table.

Usage:
    cd planning-application-project/pipeline
    python load_dummy_data.py
"""

import sys
import os
import re
import logging

# Ensure both pipeline/ and dashboard/ are importable
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, '..', 'dashboard'))

from dummy_data import load_applications, load_documents  # noqa: E402
from utilities.load import (  # noqa: E402
    get_rds_connection,
    get_council_id,
    get_status_type_id,
    get_application_type_id,
    get_document_type_id,
    load_application_to_rds,
    load_document_metadata_to_rds,
)


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def get_required_env_var(name: str) -> str:
    """
    Retrieve a required environment variable.

    Raises a ValueError if the variable is not set or is empty.
    """
    value = os.environ.get(name, "").strip()
    if value:
        return value
    msg = f"Environment variable '{name}' must be set and non-empty."
    raise ValueError(msg)

# ── RDS credentials (from environment) ───────────────────────
RDS_HOST = get_required_env_var("RDS_HOST")
RDS_PORT = int(get_required_env_var("RDS_PORT"))
RDS_USER = get_required_env_var("RDS_USER")
RDS_PASSWORD = get_required_env_var("RDS_PASSWORD")
RDS_DB_NAME = get_required_env_var("RDS_DB_NAME")
# ── Table names (matching rds-init.sql) ──────────────────────
APPLICATION_TABLE = "application"
DOCUMENT_TABLE = "document"
COUNCIL_TABLE = "council"
STATUS_TYPE_TABLE = "status_type"
APPLICATION_TYPE_TABLE = "application_type"
DOCUMENT_TYPE_TABLE = "document_type"

COUNCIL_NAME = "Tower Hamlets"

# ── Postcode regex (UK format at end of address) ─────────────
POSTCODE_RE = re.compile(r'[A-Z]{1,2}\d[\dA-Z]?\s*\d[A-Z]{2}$', re.IGNORECASE)


def extract_postcode(address: str) -> str:
    """Pull the postcode from the tail of an address string."""
    match = POSTCODE_RE.search(address)
    return match.group(0).strip() if match else ""


def main():
    # ── Load dummy data as DataFrames ────────────────────────
    apps_df = load_applications()
    docs_df = load_documents()

    # ── Connect to RDS ───────────────────────────────────────
    conn = get_rds_connection(
        RDS_HOST, RDS_PORT, RDS_USER, RDS_PASSWORD, RDS_DB_NAME)

    # ── Resolve council_id once ──────────────────────────────
    council_id = get_council_id(conn, COUNCIL_NAME, COUNCIL_TABLE)

    # ── Track dummy application_id → real DB application_id ──
    app_id_map = {}  # dummy_app_id -> db_application_id

    # ── Insert applications ──────────────────────────────────
    for _, row in apps_df.iterrows():
        dummy_id = row["application_id"]

        # Map dummy_data columns → load.py expected keys
        application_data = {
            "application_number": row["application_number"],
            "validation_date": row["date"].strftime("%Y-%m-%d"),
            "address": row["address"],
            "postcode": extract_postcode(row["address"]),
            "lat": float(row["lat"]),
            "long": float(row["long"]),
            "ai_summary": row["summary"],
            "public_interest_score": int(row["public_interest_score"]),
            "source_url": row["source_url"],
        }

        # Resolve FK ids
        status_type_id = get_status_type_id(
            conn, row["status"], STATUS_TYPE_TABLE)
        application_type_id = get_application_type_id(
            conn, row["application_type"], APPLICATION_TYPE_TABLE)

        # Insert and capture the auto-generated application_id
        db_app_id = load_application_to_rds(
            conn, APPLICATION_TABLE, application_data,
            council_id, status_type_id, application_type_id)

        app_id_map[dummy_id] = db_app_id
        logging.info(f"Mapped {dummy_id} → application_id {db_app_id}")

    # ── Insert documents ─────────────────────────────────────
    for _, row in docs_df.iterrows():
        dummy_app_id = row["application_id"]
        db_app_id = app_id_map.get(dummy_app_id)

        if db_app_id is None:
            logging.warning(
                f"No matching application for document {row['document_id']} "
                f"(application_id={dummy_app_id}). Skipping.")
            continue

        document_type_id = get_document_type_id(
            conn, row["document_type"], DOCUMENT_TYPE_TABLE)

        # Use the s3_uri from dummy data as the s3_object_key
        s3_object_key = row["s3_uri"]

        load_document_metadata_to_rds(
            conn, DOCUMENT_TABLE, db_app_id, s3_object_key, document_type_id)

    # ── Done ─────────────────────────────────────────────────
    conn.close()
    logging.info("All dummy data loaded successfully.")
    logging.info(f"  Applications inserted: {len(app_id_map)}")
    logging.info(f"  Documents inserted:    {len(docs_df)}")


if __name__ == "__main__":
    main()
