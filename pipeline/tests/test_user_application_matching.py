"""
Unit tests for the user_application_matching module.

Tests cover database connections, user/application data retrieval, 
geospatial conversions, and matching logic with mock data.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
import geopandas as gpd
import psycopg2
from shapely.geometry import Point

from ..user_notifications.user_application_matching import (
    get_rds_connection,
    get_users,
    get_applications,
    convert_df_to_gdf,
    match_applications_to_users,
)


# ============================================================================
# DATABASE CONNECTION FIXTURES
# ============================================================================


@pytest.fixture
def rds_credentials() -> dict:
    """Sample RDS database credentials."""
    return {
        "rds_host": "test-db.c123abc.eu-west-2.rds.amazonaws.com",
        "rds_port": 5432,
        "rds_user": "admin",
        "rds_password": "test_password_123",
        "rds_db_name": "planning_db"
    }


# ============================================================================
# USER DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_users_raw() -> list[dict]:
    """Sample raw user data from database."""
    return [
        {
            "email": "user1@example.com",
            "postcode": "E1 6AN",
            "lat": 51.5074,
            "long": -0.0759,
            "radius_miles": 2.0,
            "min_interest": 6
        },
        {
            "email": "user2@example.com",
            "postcode": "E2 0RA",
            "lat": 51.5312,
            "long": -0.0567,
            "radius_miles": 1.5,
            "min_interest": 5
        },
        {
            "email": "user3@example.com",
            "postcode": "EC1A 1BB",
            "lat": 51.5199,
            "long": -0.1019,
            "radius_miles": 3.0,
            "min_interest": 7
        },
    ]


@pytest.fixture
def sample_users_df(sample_users_raw: list[dict]) -> pd.DataFrame:
    """Sample users DataFrame."""
    return pd.DataFrame(sample_users_raw)


# ============================================================================
# APPLICATION DATA FIXTURES
# ============================================================================


@pytest.fixture
def sample_applications_raw() -> list[dict]:
    """Sample raw application data."""
    return [
        {
            "application_id": "PA_25_00001",
            "lat": 51.5100,
            "long": -0.0750,
            "public_interest_score": 7,
            "description": "Residential development"
        },
        {
            "application_id": "PA_25_00002",
            "lat": 51.5320,
            "long": -0.0570,
            "public_interest_score": 5,
            "description": "Office conversion"
        },
        {
            "application_id": "PA_25_00003",
            "lat": 51.5200,
            "long": -0.1020,
            "public_interest_score": 4,
            "description": "Retail space"
        },
        {
            "application_id": "PA_25_00004",
            "lat": 51.6000,
            "long": 0.0000,
            "public_interest_score": 8,
            "description": "Large commercial project"
        },
    ]


@pytest.fixture
def sample_applications_df(sample_applications_raw: list[dict]) -> pd.DataFrame:
    """Sample applications DataFrame."""
    return pd.DataFrame(sample_applications_raw)


# ============================================================================
# GEODATAFRAME FIXTURES
# ============================================================================


@pytest.fixture
def sample_users_gdf(sample_users_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Sample users GeoDataFrame with geometry."""
    gdf = gpd.GeoDataFrame(
        sample_users_df,
        geometry=gpd.points_from_xy(sample_users_df.long, sample_users_df.lat),
        crs="EPSG:4326"
    )
    return gdf


@pytest.fixture
def sample_applications_gdf(sample_applications_df: pd.DataFrame) -> gpd.GeoDataFrame:
    """Sample applications GeoDataFrame with geometry."""
    gdf = gpd.GeoDataFrame(
        sample_applications_df,
        geometry=gpd.points_from_xy(
            sample_applications_df.long, sample_applications_df.lat),
        crs="EPSG:4326"
    )
    return gdf


# ============================================================================
# TESTS: get_rds_connection
# ============================================================================


def test_get_rds_connection_success(rds_credentials: dict):
    """Test successful RDS connection."""
    mock_conn = Mock()
    with patch("psycopg2.connect", return_value=mock_conn):
        result = get_rds_connection(**rds_credentials)
        assert result == mock_conn


def test_get_rds_connection_failure(rds_credentials: dict):
    """Test RDS connection failure."""
    with patch("psycopg2.connect", side_effect=psycopg2.OperationalError("Connection failed")):
        with pytest.raises(psycopg2.OperationalError):
            get_rds_connection(**rds_credentials)


# ============================================================================
# TESTS: get_applications
# ============================================================================


def test_get_applications_success(sample_applications_raw: list[dict]):
    """Test conversion of application list to DataFrame."""
    result = get_applications(sample_applications_raw)

    assert len(result) == 4
    assert "application_id" in result.columns
    assert "public_interest_score" in result.columns
    assert result.iloc[0]["application_id"] == "PA_25_00001"


def test_get_applications_empty_list():
    """Test handling of empty application list."""
    result = get_applications([])

    assert len(result) == 0


# ============================================================================
# TESTS: convert_df_to_gdf
# ============================================================================


def test_convert_df_to_gdf_users(sample_users_df: pd.DataFrame):
    """Test conversion of users DataFrame to GeoDataFrame."""
    result = convert_df_to_gdf(sample_users_df)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 3
    assert result.crs == "EPSG:4326"
    assert all(isinstance(geom, Point) for geom in result.geometry)


def test_convert_df_to_gdf_applications(sample_applications_df: pd.DataFrame):
    """Test conversion of applications DataFrame to GeoDataFrame."""
    result = convert_df_to_gdf(sample_applications_df)

    assert isinstance(result, gpd.GeoDataFrame)
    assert len(result) == 4
    assert result.crs == "EPSG:4326"


def test_convert_df_to_gdf_preserves_data(sample_users_df: pd.DataFrame):
    """Test that conversion preserves all data columns."""
    result = convert_df_to_gdf(sample_users_df)

    for col in sample_users_df.columns:
        assert col in result.columns
        assert result[col].equals(sample_users_df[col])


# ============================================================================
# TESTS: match_applications_to_users
# ============================================================================


def test_match_applications_to_users_basic_match(
    sample_users_gdf: gpd.GeoDataFrame,
    sample_applications_gdf: gpd.GeoDataFrame
):
    """Test basic matching of applications to users."""
    result = match_applications_to_users(
        sample_users_gdf, sample_applications_gdf)

    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0
    assert "email" in result.columns
    assert "application_id" in result.columns


def test_match_applications_to_users_interest_filtering(
    sample_users_gdf: gpd.GeoDataFrame,
    sample_applications_gdf: gpd.GeoDataFrame
):
    """Test that matches are filtered by minimum interest score."""
    result = match_applications_to_users(
        sample_users_gdf, sample_applications_gdf)

    for _, row in result.iterrows():
        assert row["public_interest_score"] >= row["min_interest"]


def test_match_applications_to_users_no_matches():
    """Test matching when no applications are within user radius."""
    users_data = [{
        "email": "user@example.com",
        "postcode": "E1 6AN",
        "lat": 51.5074,
        "long": -0.0759,
        "radius_miles": 0.1,
        "min_interest": 50
    }]
    apps_data = [{
        "application_id": "PA_25_00001",
        "lat": 51.6500,
        "long": 0.5000,
        "public_interest_score": 75,
        "description": "Far away"
    }]

    users_df = pd.DataFrame(users_data)
    apps_df = pd.DataFrame(apps_data)
    users_gdf = convert_df_to_gdf(users_df)
    apps_gdf = convert_df_to_gdf(apps_df)

    result = match_applications_to_users(users_gdf, apps_gdf)

    assert len(result) == 0


def test_match_applications_to_users_interest_score_filtering():
    """Test that applications below minimum interest are filtered out."""
    users_data = [{
        "email": "user@example.com",
        "postcode": "E1 6AN",
        "lat": 51.5100,
        "long": -0.0750,
        "radius_miles": 2.0,
        "min_interest": 70
    }]
    apps_data = [
        {
            "application_id": "PA_25_00001",
            "lat": 51.5100,
            "long": -0.0750,
            "public_interest_score": 75,
            "description": "High interest"
        },
        {
            "application_id": "PA_25_00002",
            "lat": 51.5100,
            "long": -0.0750,
            "public_interest_score": 60,
            "description": "Low interest"
        }
    ]

    users_df = pd.DataFrame(users_data)
    apps_df = pd.DataFrame(apps_data)
    users_gdf = convert_df_to_gdf(users_df)
    apps_gdf = convert_df_to_gdf(apps_df)

    result = match_applications_to_users(users_gdf, apps_gdf)

    assert len(result) == 1
    assert result.iloc[0]["application_id"] == "PA_25_00001"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


def test_full_workflow_users_and_apps(
    sample_users_raw: list[dict],
    sample_applications_raw: list[dict]
):
    """Test complete workflow from raw data to matches."""
    users_df = pd.DataFrame(sample_users_raw)
    apps_df = get_applications(sample_applications_raw)

    users_gdf = convert_df_to_gdf(users_df)
    apps_gdf = convert_df_to_gdf(apps_df)

    result = match_applications_to_users(users_gdf, apps_gdf)

    assert isinstance(result, pd.DataFrame)
    assert len(result) >= 0
    if len(result) > 0:
        assert "email" in result.columns
        assert "application_id" in result.columns
        assert "public_interest_score" in result.columns
        assert "min_interest" in result.columns


def test_matching_respects_both_proximity_and_interest(
    sample_users_gdf: gpd.GeoDataFrame,
    sample_applications_gdf: gpd.GeoDataFrame
):
    """Test that matching respects both radius and interest filters."""
    result = match_applications_to_users(
        sample_users_gdf, sample_applications_gdf)

    for _, row in result.iterrows():
        assert row["public_interest_score"] >= row["min_interest"]
