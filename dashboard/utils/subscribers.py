"""Database operations for the subscribers table."""
import logging

logger = logging.getLogger(__name__)


def get_active_subscriptions(conn, email: str) -> list[dict]:
    """Return all active subscriptions for an email address."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT subscriber_id, postcode, radius_miles,
                   min_interest_score,
                   min_score_disturbance, min_score_scale,
                   min_score_housing, min_score_environment
              FROM subscribers
             WHERE email = %s AND unsubscribed_at IS NULL
            """,
            (email,),
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def deactivate_all_subscriptions(conn, email: str) -> None:
    """Soft-delete all active subscriptions for an email."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE subscribers
                   SET unsubscribed_at = NOW()
                 WHERE email = %s AND unsubscribed_at IS NULL
                """,
                (email,),
            )
        conn.commit()
        logger.info("Deactivated all subscriptions for %s", email)
    except Exception:
        conn.rollback()
        logger.exception("Failed to deactivate subscriptions for %s", email)
        raise


def deactivate_subscriptions(conn, subscriber_ids: list[int]) -> None:
    """Soft-delete specific subscriptions by their IDs."""
    if not subscriber_ids:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE subscribers
                   SET unsubscribed_at = NOW()
                 WHERE subscriber_id = ANY(%s)
                   AND unsubscribed_at IS NULL
                """,
                (subscriber_ids,),
            )
        conn.commit()
        logger.info("Deactivated %d subscription(s)", len(subscriber_ids))
    except Exception:
        conn.rollback()
        logger.exception(
            "Failed to deactivate subscriptions: %s", subscriber_ids
        )
        raise


def insert_subscriber(
    conn,
    email: str,
    postcode: str,
    lat: float,
    lon: float,
    radius_miles: float,
    min_interest_score: int,
    min_score_disturbance: int = 1,
    min_score_scale: int = 1,
    min_score_housing: int = 1,
    min_score_environment: int = 1,
) -> None:
    """Insert a new subscription row.

    Args:
        conn: Database connection
        email: Subscriber email address
        postcode: Subscriber postcode
        lat: Latitude of postcode
        lon: Longitude of postcode
        radius_miles: Notification radius in miles
        min_interest_score: Minimum overall interest score (1-5)
        min_score_disturbance: Minimum disturbance sub-score (1-5)
        min_score_scale: Minimum scale sub-score (1-5)
        min_score_housing: Minimum housing sub-score (1-5)
        min_score_environment: Minimum environment sub-score (1-5)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscribers
                    (email, postcode, lat, long, radius_miles,
                     min_interest_score,
                     min_score_disturbance, min_score_scale,
                     min_score_housing, min_score_environment)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (email, postcode, lat, lon, radius_miles,
                 min_interest_score,
                 min_score_disturbance, min_score_scale,
                 min_score_housing, min_score_environment),
            )
        conn.commit()
        logger.info(
            "New subscription for %s at %s (%.1f mi, score >= %d)",
            email, postcode, radius_miles, min_interest_score,
        )
    except Exception:
        conn.rollback()
        logger.exception("Failed to insert subscription for %s", email)
        raise
