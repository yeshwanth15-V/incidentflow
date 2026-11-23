import smtplib
import threading
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

logger = logging.getLogger(__name__)

def _send_email_thread(recipient: str, subject: str, html_body: str, text_body: str):
    """Internal helper to dispatch email via SMTP in a non-blocking thread."""
    if not Config.SMTP_ENABLED:
        logger.info(f"[Email Notification Disabled] To: {recipient} | Subject: {subject}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[IncidentFlow] {subject}"
        msg["From"] = Config.SMTP_FROM
        msg["To"] = recipient

        part1 = MIMEText(text_body, "plain")
        part2 = MIMEText(html_body, "html")
        msg.attach(part1)
        msg.attach(part2)

        if Config.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=10)
            if Config.SMTP_USE_TLS:
                server.starttls()

        if Config.SMTP_USER and Config.SMTP_PASSWORD:
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)

        server.sendmail(Config.SMTP_FROM, [recipient], msg.as_string())
        server.quit()
        logger.info(f"[Email Notification] Successfully sent email to {recipient} ({subject})")
    except Exception as e:
        logger.error(f"[Email Notification Error] Failed to send email to {recipient}: {e}")

def send_notification(recipient: str, subject: str, html_body: str, text_body: str = None):
    """
    Public asynchronous, fail-safe email dispatcher.
    Never raises an exception or interrupts incident operations.
    """
    if not recipient:
        return
    if text_body is None:
        text_body = subject
        
    thread = threading.Thread(
        target=_send_email_thread,
        args=(recipient, subject, html_body, text_body),
        daemon=True
    )
    thread.start()

def notify_incident_assigned(incident, assignee_email, assignee_name):
    """Notify team member when an incident is assigned."""
    subject = f"Assigned: {incident.reference_id} - {incident.title}"
    html = f"""
    <h3>IncidentFlow Assignment</h3>
    <p>Hello <strong>{assignee_name}</strong>,</p>
    <p>You have been assigned to incident <strong>{incident.reference_id}</strong>:</p>
    <ul>
        <li><strong>Title:</strong> {incident.title}</li>
        <li><strong>Priority:</strong> {incident.priority}</li>
        <li><strong>Category:</strong> {incident.category}</li>
        <li><strong>SLA Deadline:</strong> {incident.due_date.strftime('%Y-%m-%d %H:%M UTC') if incident.due_date else 'N/A'}</li>
    </ul>
    <p>Please log in to your dashboard to view and update this incident.</p>
    """
    text = f"You have been assigned to incident {incident.reference_id}: {incident.title}. Priority: {incident.priority}."
    send_notification(assignee_email, subject, html, text)

def notify_incident_status_changed(incident, old_status, new_status, recipient_email):
    """Notify assignee or admin when status changes."""
    subject = f"Status Update: {incident.reference_id} is now {new_status}"
    html = f"""
    <h3>Incident Status Update</h3>
    <p>Incident <strong>{incident.reference_id}</strong> ({incident.title}) status changed from <em>{old_status}</em> to <strong>{new_status}</strong>.</p>
    """
    text = f"Incident {incident.reference_id} status changed from {old_status} to {new_status}."
    send_notification(recipient_email, subject, html, text)
