"""Pipeline configuration constants.

Centralises LLM settings and scoring rubrics so that transform.py
stays focused on processing logic.
"""

LLM_MODEL = "gpt-5-nano"
MAX_PARALLEL_LLM_CALLS = 5

SUB_SCORE_RUBRICS: dict[str, str] = {
    "score_disturbance": (
        '"score_disturbance": Level of disturbance (1–5). Consider sound, spatial disruption, and air quality.\n'
        '  1 = No noticeable change. Example: internal refurbishment, like-for-like window replacement.\n'
        '  2 = Minor, short-lived disruption. Example: scaffolding for a few weeks, occasional drilling during work hours.\n'
        '  3 = Moderate disruption for several months. Example: temporary road narrowing, regular construction noise Mon–Fri, some dust.\n'
        '  4 = Significant disruption over 6+ months. Example: road closures, heavy machinery daily, noticeable dust and vibration, parking displaced.\n'
        '  5 = Severe, prolonged disruption for 1+ years. Example: major road diversions, pile-driving, demolition dust requiring air quality monitoring, loss of pavement access.'
    ),
    "score_scale": (
        '"score_scale": Scale of development (1–5). Consider the physical size and duration of works.\n'
        '  1 = Tiny, completed in days. Example: new shop sign, single tree removal, fence replacement.\n'
        '  2 = Small, completed in weeks. Example: loft conversion, single-storey rear extension, dropped kerb.\n'
        '  3 = Medium, several months. Example: two-storey side extension, conversion of house to flats, new roof.\n'
        '  4 = Large, 6–12 months. Example: new-build block of 10–50 flats, demolition and rebuild of a commercial unit.\n'
        '  5 = Major, 1+ years. Example: multi-phase estate regeneration, 100+ residential units, tower block construction.'
    ),
    "score_housing": (
        '"score_housing": Effect on local housing prices (1–5). Consider the rough potential impact based on similar developments.\n'
        '  1 = No measurable effect. Example: internal works, change of use from one shop to another.\n'
        '  2 = Negligible effect. Example: single new dwelling or conversion of house into 2 flats.\n'
        '  3 = Small but noticeable effect. Example: new block of 10–20 units, may slightly increase supply and competition.\n'
        '  4 = Moderate effect. Example: 50–100 new homes, affordable housing included, likely to shift local rental and sale prices by a few percent.\n'
        '  5 = Significant market impact. Example: 200+ units or estate regeneration that redefines the area, likely to attract new demographics and visibly move prices.'
    ),
    "score_environment": (
        '"score_environment": Environmental and community impact (1–5). Consider wildlife, community spaces, and the effect of new residents on the local area.\n'
        '  1 = No environmental or community change. Example: internal works, signage.\n'
        '  2 = Minimal impact. Example: removal of a single tree (replaced), minor change to a private garden.\n'
        '  3 = Moderate impact. Example: loss of a small green area, new residents bringing footfall to local shops but also more waste and noise.\n'
        '  4 = Notable impact. Example: building on informal green space, loss of biodiversity corridor, development near a watercourse, 50+ new residents changing the character of a quiet street.\n'
        '  5 = Major impact. Example: building on floodplain, large-scale tree removal, loss of allotments or playing fields, 200+ new residents fundamentally changing the neighbourhood feel.'
    ),
}
