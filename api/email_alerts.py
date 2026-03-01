# ---- Deadline Alert Emailer -----------------------------------------------
# Sends transactional email notifications for approaching deadlines.
# Integrates with SOL tracker and calendar events.

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "alerts@yourfirm.com")


def send_email(to: str, subject: str, html_body: str) -> bool:
    """Send a transactional email via SMTP."""
    if not SMTP_HOST:
        logger.warning("SMTP_HOST not configured — email not sent: %s", subject)
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = FROM_EMAIL
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        logger.info("✉️ Email sent: %s → %s", subject, to)
        return True
    except Exception as e:
        logger.error("Email send failed: %s", e)
        return False


def send_sol_warning(
    to: str,
    case_name: str,
    deadline: str,
    days_remaining: int,
):
    """Send SOL deadline warning email."""
    urgency = "🔴 CRITICAL" if days_remaining < 30 else "🟡 WARNING"
    subject = f"{urgency}: Statute of Limitations — {case_name} ({days_remaining} days)"

    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: {'#dc2626' if days_remaining < 30 else '#f59e0b'}; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">⚖️ Statute of Limitations Alert</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
            <p><strong>Case:</strong> {case_name}</p>
            <p><strong>SOL Deadline:</strong> {deadline}</p>
            <p><strong>Days Remaining:</strong> <span style="font-size: 24px; font-weight: bold; color: {'#dc2626' if days_remaining < 30 else '#f59e0b'};">{days_remaining}</span></p>
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 16px 0;">
            <p style="color: #6b7280; font-size: 14px;">
                This is an automated alert from your legal case management system.
                Please take immediate action if the filing has not been completed.
            </p>
        </div>
    </div>
    """
    return send_email(to, subject, html)


def send_deadline_reminder(
    to: str,
    case_name: str,
    event_title: str,
    event_date: str,
    days_until: int,
):
    """Send general deadline/event reminder email."""
    subject = f"📅 Reminder: {event_title} — {case_name} ({days_until} days)"

    html = f"""
    <div style="font-family: -apple-system, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: #6366f1; color: white; padding: 16px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">📅 Upcoming Deadline</h2>
        </div>
        <div style="border: 1px solid #e5e7eb; border-top: none; padding: 20px; border-radius: 0 0 8px 8px;">
            <p><strong>Event:</strong> {event_title}</p>
            <p><strong>Case:</strong> {case_name}</p>
            <p><strong>Date:</strong> {event_date}</p>
            <p><strong>Days Until:</strong> {days_until}</p>
        </div>
    </div>
    """
    return send_email(to, subject, html)


def check_and_send_deadline_alerts():
    """
    Scan all cases for approaching deadlines and send alerts.
    Designed to run as a scheduled task (cron/celery).
    """
    try:
        from api.deps import get_case_manager
        cm = get_case_manager()
        cases = cm.list_cases()

        alerts_sent = 0
        for case in cases:
            # Check SOL deadlines
            incident_date = case.get("incident_date")
            if incident_date:
                from api.routers.sol import SOL_PERIODS
                case_type = case.get("case_category", "").lower().replace(" ", "_")
                periods = SOL_PERIODS.get(case_type, {"default": 4})
                years = periods.get("default", 4)
                deadline = datetime.fromisoformat(incident_date) + timedelta(days=years * 365)
                days_remaining = (deadline - datetime.now()).days

                owner_email = case.get("owner_email", "")
                if 0 < days_remaining <= 90 and owner_email:
                    send_sol_warning(owner_email, case.get("name", ""), deadline.isoformat()[:10], days_remaining)
                    alerts_sent += 1

        logger.info("Deadline scan complete: %d alerts sent", alerts_sent)
        return alerts_sent

    except Exception as e:
        logger.exception("Deadline alert scan failed")
        return 0
