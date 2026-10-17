"""Small SMTP adapter for account-recovery email delivery."""
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import urlparse


class EmailConfigurationError(RuntimeError):
    """Raised when account-recovery email is not configured safely."""


def public_base_url():
    value = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc or parsed.username or parsed.password:
        raise EmailConfigurationError("PUBLIC_BASE_URL must be a trusted absolute URL.")
    if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise EmailConfigurationError("PUBLIC_BASE_URL must use HTTPS outside localhost.")
    return value


def send_totp_recovery_email(recipient, token):
    """Send a recovery link; never log or return the raw token."""
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("MAIL_FROM", "").strip()
    if not host or not sender:
        raise EmailConfigurationError("SMTP_HOST and MAIL_FROM must be configured.")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    link = f"{public_base_url()}/auth/reset_totp/{token}"

    message = EmailMessage()
    message["Subject"] = "MaterialHub authenticator recovery"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "A request was made to reset the authenticator for your MaterialHub account.\n\n"
        f"Open this link within 30 minutes to continue: {link}\n\n"
        "If you did not request this, ignore this email."
    )
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as server:
            if username:
                server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            if username:
                server.login(username, password)
            server.send_message(message)
