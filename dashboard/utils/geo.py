"""Geocoding and geospatial distance utilities."""

import math

import requests
import streamlit as st

from .config import EARTH_RADIUS_MILES, RADIUS_CIRCLE_SEGMENTS


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


def geojson_bounds(geojson: dict) -> tuple[float, float, float]:
    """Return ``(center_lat, center_lon, zoom)`` for a GeoJSON FeatureCollection.

    Computes the bounding box of all coordinates in the GeoJSON and
    derives a center point and an approximate Mapbox zoom level that
    fits the boundary comfortably.
    """
    min_lon = float("inf")
    max_lon = float("-inf")
    min_lat = float("inf")
    max_lat = float("-inf")

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        coord_type = geometry.get("type", "")
        coords = geometry.get("coordinates", [])

        if coord_type == "Polygon":
            rings = coords
        elif coord_type == "MultiPolygon":
            rings = [ring for polygon in coords for ring in polygon]
        else:
            continue

        for ring in rings:
            for lon, lat, *_ in ring:
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)

    center_lat = (min_lat + max_lat) / 2
    center_lon = (min_lon + max_lon) / 2

    # Approximate zoom from the latitude span (degrees → Mapbox zoom)
    lat_span = max_lat - min_lat
    lon_span = max_lon - min_lon
    span = max(lat_span, lon_span)

    if span <= 0:
        zoom = 14.0
    else:
        # ~360° visible at zoom 0; each zoom level halves the span
        zoom = math.log2(360 / span) - 0.5  # slight padding

    return center_lat, center_lon, round(zoom, 1)


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
