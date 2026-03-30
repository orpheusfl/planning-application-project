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
# Gradient from brand blue (#1800ad) through to brand orange (#ff751f)
# ---------------------------------------------------------------------------
SCORE_COLORS: dict[int, list[int]] = {
    1: [156, 163, 175, 160],
    2: [134, 140, 152, 170],
    3: [107, 114, 128, 180],
    4: [180, 160, 40, 190],
    5: [245, 158, 11, 200],
    6: [243, 120, 30, 210],
    7: [239, 88, 48, 220],
    8: [239, 68, 68, 230],
    9: [220, 50, 50, 240],
    10: [185, 28, 28, 250],
}
DEFAULT_MARKER_COLOR = [156, 163, 175, 180]

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
    .score-1  { background: #9CA3AF; }
    .score-2  { background: #868C98; }
    .score-3  { background: #6B7280; }
    .score-4  { background: #B4A028; }
    .score-5  { background: #F59E0B; }
    .score-6  { background: #F3781E; }
    .score-7  { background: #EF5830; }
    .score-8  { background: #EF4444; }
    .score-9  { background: #DC3232; }
    .score-10 { background: #B91C1C; }

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
