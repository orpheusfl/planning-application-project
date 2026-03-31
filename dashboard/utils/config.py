"""Shared constants and CSS for the OpenPlan dashboard."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
BRAND_BLUE = "#1800ad"
BRAND_ORANGE = "#ff751f"
BRAND_WHITE = "#ffffff"
LOGO_PATH = "openplan-logo.svg"

# ---------------------------------------------------------------------------
# Map defaults
# ---------------------------------------------------------------------------
LONDON_CENTER = {"latitude": 51.5074, "longitude": -0.1278}
MAP_ZOOM = 10
MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"

# ---------------------------------------------------------------------------
# UI behaviour
# ---------------------------------------------------------------------------
SCROLL_OFFSET_PX = 770
SCROLL_DELAY_MS = 500
CLUSTER_LIST_HEADER_PX = 197
CLUSTER_LIST_ITEM_PX = 56
SEARCH_RESULTS_LIMIT = 10

# ---------------------------------------------------------------------------
# Council boundary data
# ---------------------------------------------------------------------------
BOUNDARIES_DIR = Path(__file__).resolve().parent.parent / "boundaries"

# ---------------------------------------------------------------------------
# Sub-score (micro-interest) definitions
# ---------------------------------------------------------------------------
SUB_SCORES: list[dict[str, str]] = [
    {"column": "score_disturbance", "label": "Level of disturbance"},
    {"column": "score_scale", "label": "Scale of development"},
    {"column": "score_housing", "label": "Effect on housing prices"},
    {"column": "score_environment", "label": "Environmental & community impact"},
]

# ---------------------------------------------------------------------------
# Geo calculations
# ---------------------------------------------------------------------------
EARTH_RADIUS_MILES = 3959
RADIUS_CIRCLE_SEGMENTS = 64

# ---------------------------------------------------------------------------
# Visual mapping — public interest score → colour
# Gradient from light grey (1) to red (5)
# ---------------------------------------------------------------------------
SCORE_COLORS: dict[int, list[int]] = {
    1: [196, 196, 196, 160],
    2: [232, 168, 124, 180],
    3: [224, 112, 80, 200],
    4: [217, 68, 50, 220],
    5: [185, 28, 28, 240],
}
DEFAULT_MARKER_COLOR = [196, 196, 196, 180]

# ---------------------------------------------------------------------------
# Status badge styling
# ---------------------------------------------------------------------------
STATUS_CSS_CLASSES: dict[str, str] = {
    "pending": "status-pending",
    "consultation": "status-consultation",
    "approved": "status-approved",
    "refused": "status-refused",
}

# ---------------------------------------------------------------------------
# Global CSS injected once at page load
# ---------------------------------------------------------------------------
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .block-container { padding-top: 1rem; }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif;
        font-weight: 700;
    }

    a { color: #1800ad; }
    a:hover { color: #ff751f; }

    .status-badge {
        display: inline-block; padding: 4px 12px; border-radius: 12px;
        font-family: 'Inter', sans-serif;
        font-size: 13px; font-weight: 600;
    }
    .status-pending      { background: #FEF3C7; color: #92400E; }
    .status-consultation { background: #DBEAFE; color: #1800ad; }
    .status-approved     { background: #D1FAE5; color: #065F46; }
    .status-refused      { background: #FEE2E2; color: #991B1B; }

    .score-pill {
        display: inline-block; min-width: 28px; height: 28px;
        padding: 0 6px; border-radius: 14px;
        text-align: center; line-height: 28px; font-weight: 700;
        font-family: 'Inter', sans-serif;
        font-size: 13px; color: white;
    }
    .score-1  { background: #C4C4C4; color: #333; }
    .score-2  { background: #E8A87C; }
    .score-3  { background: #E07050; }
    .score-4  { background: #D94432; }
    .score-5  { background: #B91C1C; }

    .doc-card {
        padding: 8px 12px; border: 1px solid #E5E7EB;
        border-radius: 8px; margin-bottom: 6px;
    }
    .doc-type {
        font-family: 'Inter', sans-serif;
        font-size: 11px; color: #6B7280;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
</style>
"""
