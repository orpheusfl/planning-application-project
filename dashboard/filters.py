"""Pure DataFrame filtering functions (no Streamlit dependency)."""

import pandas as pd

from geo import haversine_miles


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


def by_radius(
    df: pd.DataFrame, lat: float, lon: float, radius_miles: float
) -> pd.DataFrame:
    """Keep applications within *radius_miles* of (*lat*, *lon*)."""
    distances = df.apply(
        lambda row: haversine_miles(lat, lon, row["lat"], row["long"]),
        axis=1,
    )
    return df[distances <= radius_miles]


def by_application_number(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Case-insensitive partial match on application number."""
    return df[
        df["application_number"].str.contains(query, case=False, na=False)
    ]
