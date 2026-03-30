"""Pure DataFrame filtering functions (no Streamlit dependency)."""

import numpy as np
import pandas as pd

from .geo import haversine_miles


def by_date(df: pd.DataFrame, start_date, end_date) -> pd.DataFrame:
    """Keep applications whose date falls within *start_date* … *end_date*."""
    return df[
        (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
    ]


def by_status(df: pd.DataFrame, status: str) -> pd.DataFrame:
    """Keep applications matching *status*, or all if ``'All'``."""
    if status == "All":
        return df
    return df[df["status"] == status]


def by_min_score(df: pd.DataFrame, min_score: int) -> pd.DataFrame:
    """Keep applications at or above *min_score*."""
    return df[df["public_interest_score"] >= min_score]


def by_min_sub_score(df: pd.DataFrame, column: str, min_score: int) -> pd.DataFrame:
    """Keep applications whose *column* sub-score is at or above *min_score*."""
    if column not in df.columns:
        return df
    return df[df[column] >= min_score]


EARTH_RADIUS_MILES = 3959


def by_radius(
    df: pd.DataFrame, lat: float, lon: float, radius_miles: float
) -> pd.DataFrame:
    """Filter applications within a radius of a given point.

    Uses vectorised NumPy haversine — significantly faster than
    row-by-row df.apply() for large DataFrames.
    """
    lat1 = np.radians(lat)
    lat2 = np.radians(df["lat"].values)
    dlat = np.radians(df["lat"].values - lat)
    dlon = np.radians(df["long"].values - lon)

    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * \
        np.cos(lat2) * np.sin(dlon / 2) ** 2
    distances = 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))

    return df[distances <= radius_miles]


def by_application_number(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Case-insensitive partial match on application number."""
    return df[
        df["application_number"].str.contains(
            query, case=False, na=False, regex=False)
    ]
