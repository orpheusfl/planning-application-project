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
    """ Fetches all users from the database. """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM subscribers;")
            users = cursor.fetchall()
            logging.info("Fetched %d users from the database.", len(users))
            df = pd.DataFrame(users, columns=[
                              "email", "postcode", "lat", "long", "radius_miles", "min_interest_score"])
            return df
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
    """ Matches applications to users based on proximity and interest score. """
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

    # Filter by minimum interest score
    matched_df = matched_df[matched_df["public_interest_score"]
                            >= matched_df["min_interest"]]

    return matched_df
