"""Email generation and delivery using AWS SES for matched applications."""

import os
import logging
import base64
from dataclasses import dataclass
from pathlib import Path

import boto3
import pandas as pd

from user_application_matching import (
    get_rds_connection,
    get_users,
    get_applications,
    convert_df_to_gdf,
    match_applications_to_users,
)

ses_client = boto3.client(
    "ses", region_name=os.getenv("AWS_REGION", "eu-west-2"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "noreply@planningwatchdog.co.uk")
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
class UserMatch:
    """Represents a user's email and their matching applications."""

    email: str
    applications: list[dict]

    def has_matches(self) -> bool:
        """Returns True if user has any matching applications."""
        return len(self.applications) > 0


def format_application_html(application: dict) -> str:
    """Formats a single application as HTML.

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

    return f"""
    <div style="border: 1px solid #e5e7eb; padding: 16px; margin: 12px 0; border-radius: 4px;">
        <h3 style="margin: 0 0 8px 0; color: #1f2937;"><a href="{url}" target="_blank" rel="noopener noreferrer">{app_id}</a></h3>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Description:</strong> {description}</p>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Interest Score:</strong> {score}/10</p>
        <p style="margin: 4px 0; color: #4b5563;"><strong>Location:</strong> {postcode}</p>
    </div>
    """


def create_email_html(applications: list[dict]) -> str:
    """Creates HTML email content with matched applications.

    Args:
        applications: List of matched applications

    Returns:
        HTML email content
    """
    application_html = "".join(format_application_html(app)
                               for app in applications)
    application_count = len(applications)
    print(applications)

    return f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #FF751F; color: white; padding: 20px; border-radius: 4px 4px 0 0; display: flex; justify-content: space-between; align-items: center; }}
            .header-text {{ flex: 1; }}
            .header-logo {{ flex-shrink: 0; margin-left: 20px; }}
            .content {{ background-color: #f9fafb; padding: 20px; border-radius: 0 0 4px 4px; }}
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


def group_applications_by_user(matched_df: pd.DataFrame) -> dict[str, list[dict]]:
    """Groups matched applications by user email.

    Args:
        matched_df: DataFrame with matched applications from user_application_matching

    Returns:
        Dictionary mapping email addresses to lists of application dictionaries
    """
    grouped = matched_df.groupby("email")
    user_applications = {}

    for email, group in grouped:
        applications = group[
            ["application_id", "description",
                "public_interest_score", "postcode_right", "application_page_url"]
        ].to_dict("records")
        user_applications[email] = applications

    return user_applications


def create_user_matches(user_applications: dict[str, list[dict]]) -> list[UserMatch]:
    """Creates UserMatch objects from grouped applications.

    Args:
        user_applications: Dictionary mapping emails to application lists

    Returns:
        List of UserMatch objects
    """
    matches = [
        UserMatch(email=email, applications=apps)
        for email, apps in user_applications.items()
    ]
    return matches


def send_notification_emails(user_matches: list[UserMatch]) -> dict:
    """Sends notification emails to users with matching applications.

    Only sends emails to users with at least one matching application.

    Args:
        user_matches: List of UserMatch objects

    Returns:
        Dictionary with send statistics
    """
    total_users = len(user_matches)
    emails_with_matches = sum(
        1 for match in user_matches if match.has_matches())
    emails_sent = 0
    emails_failed = 0

    email_subject = "New Planning Applications Matching Your Preferences"

    for user_match in user_matches:
        if not user_match.has_matches():
            logger.info("No matches for %s, skipping email", user_match.email)
            continue

        html_body = create_email_html(
            user_match.applications)
        return html_body
        send_success = send_email_via_ses(
            user_match.email,
            email_subject,
            html_body,
        )

        if send_success:
            emails_sent += 1
        else:
            emails_failed += 1

    stats = {
        "total_users_processed": total_users,
        "users_with_matches": emails_with_matches,
        "emails_sent": emails_sent,
        "emails_failed": emails_failed,
    }

    logger.info(
        "Email sending complete. Sent: %d, Failed: %d, Skipped: %d",
        stats["emails_sent"],
        stats["emails_failed"],
        total_users - emails_with_matches,
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
    print(matched_df)
    if matched_df.empty:
        logger.info("No matching applications found for any users")
        return {
            "total_users_processed": len(users_df),
            "users_with_matches": 0,
            "emails_sent": 0,
            "emails_failed": 0,
        }

    user_applications = group_applications_by_user(matched_df)
    user_matches = create_user_matches(user_applications)

    stats = send_notification_emails(user_matches)

    return stats


if __name__ == "__main__":
    # Example usage with environment variables for RDS credentials
    applications = [
        {
            "application_id": "PA/26/00515/NC",
            "lat": 51.5200,
            "long": -0.0520,
            "public_interest_score": 7,
            "description": "Residential development",
            "postcode": "SW1A 1AA",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150302&activeTab=summary"
        },
        {
            "application_id": "PA/25/00234/S",
            "lat": 51.5320,
            "long": -0.0570,
            "public_interest_score": 5,
            "description": "Office conversion",
            "postcode": "NW1 4AB",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150306&activeTab=summary"
        },
        {
            "application_id": "PA/25/00143/NC",
            "lat": 51.5200,
            "long": -0.1020,
            "public_interest_score": 4,
            "description": "Retail space",
            "postcode": "EC1A 1BB",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150307&activeTab=summary"
        },
        {
            "application_id": "PA/25/00063/S",
            "lat": 51.6000,
            "long": 0.0000,
            "public_interest_score": 8,
            "description": "Large commercial project",
            "postcode": "E1 6AN",
            "application_page_url": "https://development.towerhamlets.gov.uk/online-applications/applicationDetails.do?keyVal=DCAPR_150302&activeTab=summary"
        },
    ]
    print(generate_and_send_emails(
        'c22-planning-pipeline-db.c57vkec7dkkx.eu-west-2.rds.amazonaws.com', 5432, 'planning_admin', 'password', 'planning_db', applications))
