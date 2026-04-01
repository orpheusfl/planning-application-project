import os
import logging

import psycopg2
from psycopg2.extras import RealDictCursor
import boto3
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

ses = boto3.client("ses", region_name=os.getenv("AWS_REGION", "eu-west-2"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


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


def get_users(conn: psycopg2.extensions.connection) -> pd.DataFrame:
    """ Fetches all active subscribers from the database. """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                """SELECT email, postcode, lat, long, radius_miles,
                          min_interest_score,
                          min_score_disturbance, min_score_scale,
                          min_score_housing, min_score_environment,
                          status_preferences
                     FROM subscriber
                    WHERE unsubscribed_at IS NULL;""")
            users = cursor.fetchall()
            logging.info("Fetched %d users from the database.", len(users))
            return pd.DataFrame(users)
    except Exception as e:
        logging.error("Error fetching users: %s", e)
        raise


def get_applications(application_list: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(application_list)


def convert_df_to_gdf(df: pd.DataFrame) -> gpd.GeoDataFrame:
    """ Converts a DataFrame to a GeoDataFrame. """
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.long, df.lat),
        crs="EPSG:4326"
    )
    return gdf


def match_applications_to_users(users_gdf: gpd.GeoDataFrame, applications_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """Matches applications to users based on proximity, interest score, and sub-scores."""
    # Convert to projected CRS (meters) for accurate buffer operation
    users_projected = users_gdf.to_crs("EPSG:3857")

    # Buffer user points by radius (convert miles to meters: 1 mile ≈ 1609.34 meters)
    users_buffered = users_projected.copy()
    users_buffered.geometry = users_projected.geometry.buffer(
        users_projected["radius_miles"].astype(float) * 1609.34)

    # Convert back to geographic CRS for spatial join
    users_buffered = users_buffered.to_crs("EPSG:4326")

    # Find all applications within user radius
    matched_df = gpd.sjoin(users_buffered, applications_gdf,
                           how="inner", predicate="intersects")

    # Filter by minimum overall interest score
    matched_df = matched_df[matched_df["public_interest_score"]
                            >= matched_df["min_interest_score"]]

    # Filter by minimum sub-scores
    sub_score_filters = [
        ("score_disturbance", "min_score_disturbance"),
        ("score_scale", "min_score_scale"),
        ("score_housing", "min_score_housing"),
        ("score_environment", "min_score_environment"),
    ]
    for app_col, user_col in sub_score_filters:
        if app_col in matched_df.columns and user_col in matched_df.columns:
            matched_df = matched_df[
                matched_df[app_col] >= matched_df[user_col]
            ]

    # Filter by status preferences (comma-separated status_type names)
    if "status_preferences" in matched_df.columns and "status" in matched_df.columns:
        matched_df = _filter_by_status_preferences(matched_df)

    return matched_df


def _filter_by_status_preferences(matched_df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows whose application status matches the subscriber's preferences.

    An empty or missing status_preferences value means 'all statuses'.

    Args:
        matched_df: DataFrame with both status and status_preferences columns

    Returns:
        Filtered DataFrame
    """
    keep_mask = pd.Series(True, index=matched_df.index)

    for idx, row in matched_df.iterrows():
        prefs = row.get("status_preferences", "")
        if not prefs:
            continue
        allowed = [s.strip() for s in prefs.split(",")]
        if row["status"] not in allowed:
            keep_mask[idx] = False

    return matched_df[keep_mask]
