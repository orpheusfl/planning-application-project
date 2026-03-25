"""Database operations for the subscribers table."""


def get_active_subscriptions(conn, email: str) -> list[dict]:
    """Return all active subscriptions for an email address."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT subscriber_id, postcode, radius_miles, min_interest_score
              FROM subscribers
             WHERE email = %s AND unsubscribed_at IS NULL
            """,
            (email,),
        )
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def deactivate_all_subscriptions(conn, email: str) -> None:
    """Soft-delete all active subscriptions for an email."""
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


def insert_subscriber(
    conn,
    email: str,
    postcode: str,
    lat: float,
    lon: float,
    radius_miles: float,
    min_interest_score: int,
) -> None:
    """Insert a new subscription row."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO subscribers
                (email, postcode, lat, long, radius_miles, min_interest_score)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (email, postcode, lat, lon, radius_miles, min_interest_score),
        )
    conn.commit()
