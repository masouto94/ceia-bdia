"""Minimal SMTP/Mailpit sender; callers never log recovery secrets."""

from email.message import EmailMessage
import smtplib

from app.core.config import settings


def send_recovery(email: str, token: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = email
    message["Subject"] = "Recuperación de contraseña"
    message.set_content(f"Restablecé tu contraseña: {settings.web_public_url}/reset-password?token={token}")
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
        smtp.send_message(message)
