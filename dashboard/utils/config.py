"""Shared constants and CSS for the OpenPlan dashboard."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
BRAND_BLUE = "#165A9E"
BRAND_ORANGE = "#F08B21"
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
# Sub-score (interest category) definitions
# ---------------------------------------------------------------------------
SUB_SCORES: list[dict[str, str]] = [
    {
        "column": "score_disturbance",
        "label": "Level of disturbance",
        "help": "How much noise, dust, or disruption the development may cause to nearby residents.",
    },
    {
        "column": "score_scale",
        "label": "Scale of development",
        "help": "The size and scope of the proposed development, from minor alterations to major construction.",
    },
    {
        "column": "score_housing",
        "label": "Effect on housing prices",
        "help": "The potential impact on local property values and housing affordability.",
    },
    {
        "column": "score_environment",
        "label": "Environmental & community impact",
        "help": "Effects on green spaces, air quality, traffic, and community facilities.",
    },
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
    "permit": "status-approved",
    "refuse": "status-refused",
}

# ---------------------------------------------------------------------------
# Global CSS injected once at page load
# ---------------------------------------------------------------------------
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * {
        font-family: 'Inter', sans-serif !important;
    }

    /* Preserve Material Icons */
    .material-symbols-rounded,
    .material-icons,
    [class*="icon"],
    [data-testid="stIconMaterial"] {
        font-family: 'Material Symbols Rounded' !important;
    }

    .block-container { padding-top: 1rem; }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F08B21;
    }

    /* Smaller font for sidebar expander labels */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p {
        font-size: 13px;
    }

    /* Expander header and details background */
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background-color: #efad68 !important;
    }

    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] {
        background-color: #efad68 !important;
    }

    /* Subscribe button background */
    [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
        background-color: #efad68 !important;
        border-color: #efad68 !important;
    }

    /* Solid green for success alerts in sidebar */
    [data-testid="stSidebar"] [data-testid="stAlertContainer"] {
        background-color: #D1FAE5 !important;
    }

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

    /* Floating chat button */
    .st-key-chat_fab {
        position: fixed;
        bottom: 2rem;
        right: 2rem;
        z-index: 999;
    }
    .st-key-chat_fab button {
        border-radius: 50% !important;
        width: 56px !important;
        height: 56px !important;
        padding: 0 !important;
        font-size: 24px !important;
        background-color: #165A9E !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.25) !important;
        cursor: pointer;
    }
    .st-key-chat_fab button:hover {
        background-color: #0e4a82 !important;
        box-shadow: 0 6px 16px rgba(0,0,0,0.35) !important;
    }

    /* Floating chat overlay panel */
    .st-key-chat_overlay {
        position: fixed;
        bottom: 6rem;
        right: 2rem;
        z-index: 998;
        width: 420px;
        max-height: 70vh;
        background: white;
        border-radius: 12px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.2);
        overflow-y: auto;
        display: flex;
        flex-direction: column;
    }
    .st-key-chat_overlay > div {
        padding: 0.5rem 0.75rem;
    }
    .st-key-chat_overlay .stSelectbox,
    .st-key-chat_overlay .stTextInput {
        margin-bottom: 0.25rem;
    }
    .st-key-chat_overlay [data-testid="stVerticalBlock"] {
        gap: 0.4rem;
    }
    .st-key-chat_overlay [data-testid="stChatMessage"] p {
        font-size: 13px !important;
    }
    .st-key-chat_overlay .stFormSubmitButton button,
    .st-key-chat_overlay .st-key-chat_clear button {
        font-size: 12px !important;
        padding: 0.2rem 0.5rem !important;
        min-height: 0 !important;
        height: auto !important;
    }
</style>
"""
