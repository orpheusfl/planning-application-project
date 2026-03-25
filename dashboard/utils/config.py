"""Shared constants and CSS for the Planning Watchdog dashboard."""

# ---------------------------------------------------------------------------
# Map defaults
# ---------------------------------------------------------------------------
TOWER_HAMLETS_CENTER = {"latitude": 51.5200, "longitude": -0.0500}
MAP_ZOOM = 13
MAP_STYLE = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json"

# ---------------------------------------------------------------------------
# UI behaviour
# ---------------------------------------------------------------------------
SCROLL_OFFSET_PX = 770
SCROLL_DELAY_MS = 500
SEARCH_RESULTS_LIMIT = 10

# ---------------------------------------------------------------------------
# Geo calculations
# ---------------------------------------------------------------------------
EARTH_RADIUS_MILES = 3959
RADIUS_CIRCLE_SEGMENTS = 64

# ---------------------------------------------------------------------------
# Visual mapping — public interest score → colour
# ---------------------------------------------------------------------------
SCORE_COLORS: dict[int, list[int]] = {
    1: [156, 163, 175, 180],
    2: [107, 114, 128, 180],
    3: [245, 158, 11, 200],
    4: [239, 68, 68, 220],
    5: [220, 38, 38, 240],
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
    .block-container { padding-top: 1rem; }

    .status-badge {
        display: inline-block; padding: 4px 12px; border-radius: 12px;
        font-size: 13px; font-weight: 600;
    }
    .status-pending      { background: #FEF3C7; color: #92400E; }
    .status-consultation { background: #DBEAFE; color: #1E40AF; }
    .status-approved     { background: #D1FAE5; color: #065F46; }
    .status-refused      { background: #FEE2E2; color: #991B1B; }

    .score-pill {
        display: inline-block; width: 28px; height: 28px; border-radius: 50%;
        text-align: center; line-height: 28px; font-weight: 700;
        font-size: 14px; color: white;
    }
    .score-1 { background: #9CA3AF; }
    .score-2 { background: #6B7280; }
    .score-3 { background: #F59E0B; }
    .score-4 { background: #EF4444; }
    .score-5 { background: #DC2626; }

    .doc-card {
        padding: 8px 12px; border: 1px solid #E5E7EB;
        border-radius: 8px; margin-bottom: 6px;
    }
    .doc-type {
        font-size: 11px; color: #6B7280;
        text-transform: uppercase; letter-spacing: 0.5px;
    }
</style>
"""
