from __future__ import annotations

import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


def email_is_configured() -> bool:
    settings = get_settings()
    return settings.email_enabled and bool(settings.smtp_host.strip())


async def send_email(*, to: str, subject: str, body: str) -> bool:
    """Send plain-text email. Returns True if sent, False if skipped."""
    settings = get_settings()
    if not email_is_configured():
        logger.debug("email_skipped", to=to, subject=subject, reason="not_configured")
        return False

    import aiosmtplib

    message = f"From: {settings.smtp_from}\r\nTo: {to}\r\nSubject: {subject}\r\n\r\n{body}"
    await aiosmtplib.send(
        message,
        sender=settings.smtp_from,
        recipients=[to],
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
    )
    logger.info("email_sent", to=to, subject=subject)
    return True
