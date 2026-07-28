"""
mailer.py
---------
Sends notification emails to the correct service-branch inbox once a
complaint has been classified by the NLP model.

Uses Gmail SMTP (smtp.gmail.com:465, SSL) with an App Password.
Credentials are read from Streamlit secrets:

    [email]
    sender = "pramidibalu2005@gmail.com"
    app_password = "xxxx xxxx xxxx xxxx"   # 16-char Gmail App Password

NOTE: Gmail requires an "App Password" (not your normal login
password) when 2FA is enabled -- generate one at
https://myaccount.google.com/apppasswords
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st


def _get_credentials():
    try:
        sender = st.secrets["email"]["sender"]
        app_password = st.secrets["email"]["app_password"]
        return sender, app_password
    except Exception:
        return None, None


def send_complaint_email(receiver_email, user_name, user_id, branch, sub_service,
                          message, confidence, extra_recipients=None):
    """
    receiver_email may be a single string or a list of strings
    (Community branch has two recipients).
    extra_recipients: optional list of individual service-team member
    emails (added by Admin for this exact branch/sub_service) who should
    also be notified, in addition to the generic branch inbox(es).
    """
    sender, app_password = _get_credentials()
    if not sender or not app_password:
        return False, "Email credentials not configured in secrets.toml -- skipped sending."

    if isinstance(receiver_email, str):
        recipients = [receiver_email]
    else:
        recipients = list(receiver_email)

    if extra_recipients:
        for email in extra_recipients:
            if email and email not in recipients:
                recipients.append(email)

    subject = f"[New Complaint] {branch} / {sub_service} - User {user_id}"
    body = f"""A new complaint has been routed to your team.

Branch:        {branch}
Sub-Service:   {sub_service}
User ID:       {user_id}
User Name:     {user_name}
Classifier Confidence: {confidence}

Message:
--------
{message}

--
Automated notification from US Housing Support System
"""

    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, app_password)
            server.sendmail(sender, recipients, msg.as_string())
        return True, f"Email sent to {', '.join(recipients)}"
    except Exception as e:
        return False, f"Failed to send email: {e}"


def send_new_service_member_email(member_email, member_name, member_id, branch, sub_service):
    """Notifies a newly added service team member that their account
    has been created, along with their login details (ID/branch/sub-service)."""
    sender, app_password = _get_credentials()
    if not sender or not app_password:
        return False, "Email credentials not configured in secrets.toml -- skipped sending."

    subject = f"Welcome to the {branch} / {sub_service} Team"
    body = f"""Hi {member_name},

You have been added as a Service Team member for the US Housing Support System.

Login details:
  Member ID:   {member_id}
  Branch:      {branch}
  Sub-Service: {sub_service}

Log in to the Service Team page using these details to view and resolve
tickets routed to your queue.

--
Automated notification from US Housing Support System
"""
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = member_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, app_password)
            server.sendmail(sender, [member_email], msg.as_string())
        return True, f"Welcome email sent to {member_email}"
    except Exception as e:
        return False, f"Failed to send welcome email: {e}"


def send_complaint_approved_email(receiver_email, user_name, user_id, branch, sub_service,
                                   message, confidence, priority, extra_recipients=None):
    """Sent to the service team once Admin approves a low-confidence
    complaint that was held for manual review. extra_recipients: optional
    list of individual service-team member emails for this exact
    branch/sub_service, notified in addition to the generic branch inbox."""
    sender, app_password = _get_credentials()
    if not sender or not app_password:
        return False, "Email credentials not configured in secrets.toml -- skipped sending."

    recipients = [receiver_email] if isinstance(receiver_email, str) else list(receiver_email)
    if extra_recipients:
        for email in extra_recipients:
            if email and email not in recipients:
                recipients.append(email)

    subject = f"[Admin-Approved Complaint] {branch} / {sub_service} - User {user_id}"
    body = f"""An Admin-reviewed complaint has been approved and routed to your team.

Branch:        {branch}
Sub-Service:   {sub_service}
Priority:      {priority}
User ID:       {user_id}
User Name:     {user_name}
Original Classifier Confidence: {confidence} (was below auto-accept threshold)

Message:
--------
{message}

--
Automated notification from US Housing Support System
"""
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender, app_password)
            server.sendmail(sender, recipients, msg.as_string())
        return True, f"Email sent to {', '.join(recipients)}"
    except Exception as e:
        return False, f"Failed to send email: {e}"
