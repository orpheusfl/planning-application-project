"""Tests for dummy_data — schema and integrity of fixture data."""

import pandas as pd
import pytest

from dummy_data import load_applications, load_documents


class TestLoadApplications:
    """Tests for dummy_data.load_applications."""

    def test_returns_dataframe(self):
        df = load_applications()
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = load_applications()
        required = {
            "application_id",
            "application_number",
            "address",
            "lat",
            "long",
            "date",
            "status",
            "application_type",
            "summary",
            "public_interest_score",
            "additional_notes",
            "source_url",
        }
        assert required.issubset(set(df.columns))

    def test_not_empty(self):
        df = load_applications()
        assert not df.empty

    def test_date_column_is_datetime(self):
        df = load_applications()
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_application_ids_are_unique(self):
        df = load_applications()
        assert df["application_id"].is_unique

    def test_application_numbers_are_unique(self):
        df = load_applications()
        assert df["application_number"].is_unique

    def test_lat_lon_are_numeric(self):
        df = load_applications()
        assert pd.api.types.is_numeric_dtype(df["lat"])
        assert pd.api.types.is_numeric_dtype(df["long"])

    def test_lat_lon_in_valid_range(self):
        df = load_applications()
        assert all(-90 <= df["lat"]) and all(df["lat"] <= 90)
        assert all(-180 <= df["long"]) and all(df["long"] <= 180)

    def test_scores_in_valid_range(self):
        df = load_applications()
        assert all(df["public_interest_score"].between(1, 5))

    def test_no_null_required_fields(self):
        df = load_applications()
        for col in ["application_id", "application_number", "address",
                    "lat", "long", "date", "status", "public_interest_score"]:
            assert df[col].notna().all(
            ), f"Null found in required column {col}"


class TestLoadDocuments:
    """Tests for dummy_data.load_documents."""

    def test_returns_dataframe(self):
        df = load_documents()
        assert isinstance(df, pd.DataFrame)

    def test_has_required_columns(self):
        df = load_documents()
        required = {
            "document_id",
            "application_id",
            "document_name",
            "document_type",
            "s3_uri",
            "source_url",
        }
        assert required.issubset(set(df.columns))

    def test_not_empty(self):
        df = load_documents()
        assert not df.empty

    def test_document_ids_are_unique(self):
        df = load_documents()
        assert df["document_id"].is_unique

    def test_no_null_fields(self):
        df = load_documents()
        for col in df.columns:
            assert df[col].notna().all(), f"Null found in column {col}"

    def test_all_application_ids_reference_valid_apps(self):
        apps = load_applications()
        docs = load_documents()
        valid_ids = set(apps["application_id"])
        doc_app_ids = set(docs["application_id"])
        orphans = doc_app_ids - valid_ids
        assert not orphans, f"Documents reference non-existent apps: {orphans}"

    def test_s3_uris_have_correct_prefix(self):
        df = load_documents()
        assert all(df["s3_uri"].str.startswith("s3://"))
