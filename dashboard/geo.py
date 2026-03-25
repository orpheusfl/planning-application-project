"""Geocoding and geospatial distance utilities."""

import math

import requests
import streamlit as st

from config import EARTH_RADIUS_MILES, RADIUS_CIRCLE_SEGMENTS


@st.cache_data(ttl=3600)
def geocode_postcode(postcode: str) -> tuple[float, float] | None:
    """Convert a UK postcode to (lat, lon) via postcodes.io.

    Results are cached for one hour to avoid repeated API calls.
    Returns ``None`` when the postcode cannot be resolved.
    """
    try:
        resp = requests.get(
            f"https://api.postcodes.io/postcodes/{postcode.strip()}",
            timeout=5,
        )
        data = resp.json()
        if data["status"] == 200:
            return data["result"]["latitude"], data["result"]["longitude"]
    except requests.RequestException:
        pass
    return None


def haversine_miles(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return the great-circle distance in miles between two points."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def generate_circle_polygon(
    lat: float, lon: float, radius_miles: float
) -> list[list[float]]:
    """Return a closed ring of ``[lon, lat]`` pairs approximating a circle."""
    radius_km = radius_miles * 1.60934
    points: list[list[float]] = []
    for i in range(RADIUS_CIRCLE_SEGMENTS + 1):
        angle = math.radians(360 * i / RADIUS_CIRCLE_SEGMENTS)
        dlat = radius_km / 111.32 * math.cos(angle)
        dlon = radius_km / (111.32 * math.cos(math.radians(lat))) * math.sin(
            angle
        )
        points.append([lon + dlon, lat + dlat])
    return points
