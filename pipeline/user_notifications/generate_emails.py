"""Email generation and delivery using AWS SES for matched applications."""

import os
import logging
import base64
from dataclasses import dataclass
from pathlib import Path

import boto3
import pandas as pd
import dotenv

from user_application_matching import (
    get_rds_connection,
    get_users,
    get_applications,
    convert_df_to_gdf,
    match_applications_to_users,
)

dotenv.load_dotenv()  # Load environment variables from .env file

ses_client = boto3.client(
    "ses", region_name=os.getenv("AWS_REGION", "eu-west-2"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv(
    "SENDER_EMAIL")
LOGO_PATH = Path(__file__).parent / "OpenPlan_Logo.png"


def get_logo_base64() -> str:
    """Loads the logo and converts it to base64 data URI.

    Returns:
        Base64 encoded data URI for the logo
    """
    if not LOGO_PATH.exists():
        logger.warning("Logo file not found at %s", LOGO_PATH)
        return ""

    with open(LOGO_PATH, "rb") as f:
        logo_data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{logo_data}"


@dataclass
class SubscriptionMatch:
    """Represents a subscription and its matching applications."""

    email: str
    postcode: str
    radius_miles: float
    min_interest_score: int
    min_score_disturbance: int
    min_score_scale: int
    min_score_housing: int
    min_score_environment: int
    applications: list[dict]
    status_preferences: str = ""

    def has_matches(self) -> bool:
        """Returns True if subscription has any matching applications."""
        return len(self.applications) > 0


def _format_display_status(application: dict) -> str:
    """Build the compound display status for an application.

    Returns 'Decided - Permit' style when a decision exists,
    otherwise the plain status type.
    """
    status = application.get("status", "")
    decision = application.get("decision", "")
    if status == "Decided" and decision:
        return f"{status} - {decision}"
    return status


def format_application_html(application: dict) -> str:
    """Formats a single application as HTML including sub-scores.

    Args:
        application: Dictionary containing application details

    Returns:
        HTML string representing the application
    """
    app_id = application.get("application_id", "N/A")
    description = application.get("description", "No description available")
    score = application.get("public_interest_score", "N/A")
    postcode = application.get("postcode_right", "N/A")
    url = application.get("application_page_url", "#")
    display_status = _format_display_status(application)

    disturbance = application.get("score_disturbance", "N/A")
    scale = application.get("score_scale", "N/A")
    housing = application.get("score_housing", "N/A")
    environment = application.get("score_environment", "N/A")

    return f"""
    <div style="border: 1px solid #e5e7eb; padding: 16px; margin: 12px 0; border-radius: 4px;">
        <h3 style="margin: 0 0 8px 0; color: #1f2937;"><a href="{url}" target="_blank" rel="noopener noreferrer" style="color: #1800ad;">{app_id}</a></h3>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Status:</strong> {display_status}</p>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Description:</strong> {description}</p>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Interest Score:</strong> {score}/5</p>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Location:</strong> {postcode}</p>
        <div style="margin: 8px 0 0 0; padding: 8px; background: #f3f4f6; border-radius: 4px;">
            <p style="margin: 0 0 4px 0; font-weight: 600; color: #374151; font-size: 13px;">Interest Category Scores</p>
            <table style="width: 100%; font-size: 13px; color: #4b5563;">
                <tr><td>Disturbance</td><td style="text-align: right; font-weight: 600;">{disturbance}/5</td></tr>
                <tr><td>Scale of development</td><td style="text-align: right; font-weight: 600;">{scale}/5</td></tr>
                <tr><td>Effect on housing prices</td><td style="text-align: right; font-weight: 600;">{housing}/5</td></tr>
                <tr><td>Environmental &amp; community impact</td><td style="text-align: right; font-weight: 600;">{environment}/5</td></tr>
            </table>
        </div>
    </div>
    """


def format_preferences_footer_html(subscription: SubscriptionMatch) -> str:
    """Builds HTML for the subscriber preferences footer.

    Only includes score preferences where the minimum threshold is greater than 1.

    Args:
        subscription: The SubscriptionMatch containing user preferences

    Returns:
        HTML string for the preferences footer section
    """
    preference_rows: list[str] = []

    preference_rows.append(
        f'<tr><td style="padding: 4px 0;">Search radius</td>'
        f'<td style="text-align: right; padding: 4px 0; font-weight: 600;">{subscription.radius_miles} miles from {subscription.postcode}</td></tr>'
    )

    if subscription.status_preferences:
        statuses = subscription.status_preferences.split(",")
        status_display = ", ".join(statuses)
        preference_rows.append(
            f'<tr><td style="padding: 4px 0;">Status types</td>'
            f'<td style="text-align: right; padding: 4px 0;'
            f' font-weight: 600;">{status_display}</td></tr>'
        )

    score_preferences = [
        ("Overall interest score", subscription.min_interest_score),
        ("Disturbance", subscription.min_score_disturbance),
        ("Scale of development", subscription.min_score_scale),
        ("Effect on housing prices", subscription.min_score_housing),
        ("Environmental &amp; community impact",
         subscription.min_score_environment),
    ]

    for label, value in score_preferences:
        if value <= 1:
            continue
        preference_rows.append(
            f'<tr><td style="padding: 4px 0;">{label}</td>'
            f'<td style="text-align: right; padding: 4px 0; font-weight: 600;">≥ {value}/5</td></tr>'
        )

    rows_html = "\n".join(preference_rows)

    return f"""
    <div style="background: #165A9E; color: white; padding: 20px; border-radius: 0 0 4px 4px; margin-top: 0;">
        <p style="margin: 0 0 8px 0; font-weight: 600; font-size: 14px;">Your Notification Preferences</p>
        <table style="width: 100%; font-size: 13px; color: rgba(255,255,255,0.9);">
            {rows_html}
        </table>
        <p style="margin: 12px 0 0 0; font-size: 11px; color: rgba(255,255,255,0.6);">
            Manage your preferences in the Open Plan dashboard.
        </p>
    </div>
    """


def create_email_html(applications: list[dict], subscription: SubscriptionMatch) -> str:
    """Creates HTML email content with matched applications and subscriber preferences.

    Args:
        applications: List of matched applications
        subscription: The SubscriptionMatch containing user preferences

    Returns:
        HTML email content
    """
    application_html = "".join(format_application_html(app)
                               for app in applications)
    application_count = len(applications)
    preferences_html = format_preferences_footer_html(subscription)

    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #F08B21; color: white; padding: 20px; border-radius: 4px 4px 0 0; display: flex; justify-content: space-between; align-items: center; }}
            .header-text {{ flex: 1; }}
            .header-logo {{ flex-shrink: 0; margin-left: 20px; }}
            .content {{ background-color: #f9fafb; padding: 20px; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #6b7280; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-text">
                    <p style="margin: 8px 0 0 0;">New Applications Matching Your Preferences</p>
                </div>
                <div class="header-logo">
                    <img src="{get_logo_base64()}" alt="Open Plan logo" style="max-height: 60px;">
                </div>
            </div>
            <div class="content">
                <p>Hi,</p>
                <p>We found <strong>{application_count}</strong> new planning application(s) matching your preferences:</p>
                {application_html}
                <p style="margin-top: 20px; color: black; font-size: 14px;">
                    Review these applications and manage your preferences in the Open Plan dashboard.
                </p>
            </div>
            {preferences_html}
            <div class="footer">
                <p>Open Plan | Letting you know what's happening in your neighbourhood before it happens</p>
            </div>
        </div>
    </body>
    </html>
    """


def send_email_via_ses(recipient_email: str, subject: str, html_body: str) -> bool:
    """Sends an email using AWS SES.

    Args:
        recipient_email: Recipient's email address
        subject: Email subject line
        html_body: HTML email body

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        response = ses_client.send_email(
            Source=SENDER_EMAIL,
            Destination={"ToAddresses": [recipient_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Html": {"Data": html_body}},
            },
        )
        logger.info(
            "Email sent to %s. Message ID: %s",
            recipient_email,
            response["MessageId"],
        )
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", recipient_email, e)
        return False


def group_applications_by_subscription(matched_df: pd.DataFrame) -> dict[tuple, list[dict]]:
    """Groups matched applications by subscription.

    Each subscription is uniquely identified by email, radius_miles, and score preferences.
    This ensures users with multiple subscriptions receive separate emails per subscription.

    Args:
        matched_df: DataFrame with matched applications from user_application_matching

    Returns:
        Dictionary mapping subscription key tuples to application lists
    """
    subscription_cols = [
        "email", "postcode", "radius_miles", "min_interest_score",
        "min_score_disturbance", "min_score_scale",
        "min_score_housing", "min_score_environment",
        "status_preferences",
    ]
    grouped = matched_df.groupby(subscription_cols)
    subscriptions = {}

    application_cols = [
        "application_id", "description",
        "public_interest_score",
        "score_disturbance", "score_scale",
        "score_housing", "score_environment",
        "postcode_right", "application_page_url",
        "status", "decision",
    ]
    available_cols = [c for c in application_cols if c in matched_df.columns]

    for key, group in grouped:
        applications = group[available_cols].to_dict("records")
        subscriptions[key] = applications

    return subscriptions


def create_subscription_matches(subscriptions: dict[tuple, list[dict]]) -> list[SubscriptionMatch]:
    """Creates SubscriptionMatch objects from grouped subscriptions.

    Args:
        subscriptions: Dictionary mapping subscription tuples to application lists

    Returns:
        List of SubscriptionMatch objects
    """
    matches = []
    for key, apps in subscriptions.items():
        (email, postcode, radius, min_int,
         min_dist, min_scale, min_housing, min_env,
         status_prefs) = key
        matches.append(
            SubscriptionMatch(
                email=email,
                postcode=postcode,
                radius_miles=radius,
                min_interest_score=min_int,
                min_score_disturbance=min_dist,
                min_score_scale=min_scale,
                min_score_housing=min_housing,
                min_score_environment=min_env,
                applications=apps,
                status_preferences=status_prefs if status_prefs else "",
            )
        )
    return matches


def send_notification_emails(subscription_matches: list[SubscriptionMatch]) -> dict:
    """Sends notification emails to subscriptions with matching applications.

    Only sends emails to subscriptions with at least one matching application.

    Args:
        subscription_matches: List of SubscriptionMatch objects

    Returns:
        Dictionary with send statistics
    """
    total_subscriptions = len(subscription_matches)
    subscriptions_with_matches = sum(
        1 for match in subscription_matches if match.has_matches())
    emails_sent = 0
    emails_failed = 0

    email_subject = "New Planning Applications Matching Your Preferences"

    for subscription_match in subscription_matches:
        if not subscription_match.has_matches():
            logger.info(
                "No matches for subscription %s (radius: %.1f mi, min_score: %d), skipping email",
                subscription_match.email,
                subscription_match.radius_miles,
                subscription_match.min_interest_score,
            )
            continue

        html_body = create_email_html(
            subscription_match.applications, subscription_match)
        send_success = send_email_via_ses(
            subscription_match.email,
            email_subject,
            html_body,
        )

        if send_success:
            emails_sent += 1
        else:
            emails_failed += 1
    stats = {
        "total_subscriptions_processed": total_subscriptions,
        "subscriptions_with_matches": subscriptions_with_matches,
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
    }

    logger.info(
        "Email sending complete. Sent: %d, Failed: %d, Skipped: %d",
        stats["emails_sent"],
        stats["emails_failed"],
        total_subscriptions - subscriptions_with_matches,
    )

    return stats


def generate_and_send_emails(
    rds_host: str,
    rds_port: int,
    rds_user: str,
    rds_password: str,
    rds_db_name: str,
    applications_list: list[dict],
) -> dict:
    """Main function to generate and send emails to matched users.

    Orchestrates the entire process:
    1. Fetches users from RDS
    2. Matches applications to users based on preferences
    3. Sends emails to users with matches

    Args:
        rds_host: RDS database host
        rds_port: RDS database port
        rds_user: RDS database user
        rds_password: RDS database password
        rds_db_name: RDS database name
        applications_list: List of application dictionaries

    Returns:
        Dictionary with email sending statistics
    """
    try:
        conn = get_rds_connection(
            rds_host, rds_port, rds_user, rds_password, rds_db_name)
        users_df = get_users(conn)
        conn.close()
    except Exception as e:
        logger.error("Failed to fetch users from RDS: %s", e)
        raise

    applications_df = get_applications(applications_list)

    users_gdf = convert_df_to_gdf(users_df)
    applications_gdf = convert_df_to_gdf(applications_df)

    matched_df = match_applications_to_users(users_gdf, applications_gdf)
    if matched_df.empty:
        logger.info("No matching applications found for any subscriptions")
        return {
            "total_subscriptions_processed": len(users_df),
            "subscriptions_with_matches": 0,
            "emails_sent": 0,
            "emails_failed": 0,
        }

    subscriptions = group_applications_by_subscription(matched_df)
    subscription_matches = create_subscription_matches(subscriptions)

    stats = send_notification_emails(subscription_matches)

    return stats


def preview_example_email() -> None:
    """Generates an example subscriber email and writes it to an HTML file for browser preview."""
    example_applications = [
        {
            "application_id": "PA/26/00515/NC",
            "public_interest_score": 4,
            "description": "Construction of a three-storey residential block comprising 12 flats with associated parking and landscaping.",
            "postcode_right": "SW1A 1AA",
            "score_disturbance": 4,
            "score_scale": 3,
            "score_housing": 5,
            "score_environment": 2,
            "status": "Decided",
            "decision": "Permit",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150302&activeTab=summary",
        },
        {
            "application_id": "PA/25/00234/S",
            "public_interest_score": 3,
            "description": "Change of use from office (Class E) to 6 residential units (Class C3) with rear extension.",
            "postcode_right": "NW1 4AB",
            "score_disturbance": 2,
            "score_scale": 2,
            "score_housing": 4,
            "score_environment": 3,
            "status": "Registered",
            "decision": "",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150306&activeTab=summary",
        },
        {
            "application_id": "PA/25/00143/NC",
            "public_interest_score": 5,
            "description": "Demolition of existing warehouse and erection of a mixed-use development including 40 residential units and ground-floor retail.",
            "postcode_right": "EC1A 1BB",
            "score_disturbance": 5,
            "score_scale": 5,
            "score_housing": 4,
            "score_environment": 3,
            "status": "Decided",
            "decision": "Refuse",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150307&activeTab=summary",
        },
    ]

    example_subscription = SubscriptionMatch(
        email="subscriber@example.com",
        postcode="E1 6AN",
        radius_miles=1.5,
        min_interest_score=3,
        min_score_disturbance=2,
        min_score_scale=1,
        min_score_housing=3,
        min_score_environment=1,
        applications=example_applications,
        status_preferences="Decided,Registered",
    )

    html_content = create_email_html(
        example_applications, example_subscription)
    output_path = Path(__file__).parent / "email_preview.html"
    output_path.write_text(html_content, encoding="utf-8")
    print(f"Email preview written to: {output_path}")
    print(f"Open in browser: file://{output_path}")


if __name__ == "__main__":
    preview_example_email()
