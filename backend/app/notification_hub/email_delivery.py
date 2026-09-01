from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailDeliveryConfig:
    """All values come from the environment, never a request payload or a
    default -- same discipline as every other credential-backed component
    in this build. Uses standard SMTP (works with Gmail app passwords,
    most transactional-email providers, or a self-hosted relay) rather
    than a specific vendor API, so it isn't locked to one provider."""

    smtp_host: str | None = field(default_factory=lambda: os.getenv("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_username: str | None = field(default_factory=lambda: os.getenv("SMTP_USERNAME"))
    smtp_password: str | None = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))
    from_address: str | None = field(default_factory=lambda: os.getenv("NOTIFICATION_EMAIL_FROM"))
    to_address: str | None = field(default_factory=lambda: os.getenv("NOTIFICATION_EMAIL_TO"))
    use_starttls: bool = True
    timeout_seconds: float = 15.0


class SmtpEmailDeliveryClient:
    """The one component allowed to actually send an email -- a real SMTP
    connection, not a simulation. Fails closed: any missing required
    setting, or any SMTP-level error, raises rather than silently
    pretending delivery succeeded.
    """

    def __init__(self, config: EmailDeliveryConfig | None = None, smtp_factory=None) -> None:
        self.config = config or EmailDeliveryConfig()
        # Injectable for tests -- a real smtplib.SMTP connection is a live
        # network client, not something httpx.MockTransport can stand in for.
        self._smtp_factory = smtp_factory or (
            lambda: smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=self.config.timeout_seconds)
        )

    def send(self, subject: str, body: str) -> None:
        missing = [
            name
            for name, value in (
                ("SMTP_HOST", self.config.smtp_host),
                ("SMTP_USERNAME", self.config.smtp_username),
                ("SMTP_PASSWORD", self.config.smtp_password),
                ("NOTIFICATION_EMAIL_FROM", self.config.from_address),
                ("NOTIFICATION_EMAIL_TO", self.config.to_address),
            )
            if not value
        ]
        if missing:
            raise EmailDeliveryError(f"Missing required email settings: {', '.join(missing)}")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.config.from_address
        message["To"] = self.config.to_address
        message.set_content(body)

        try:
            with self._smtp_factory() as smtp:
                if self.config.use_starttls:
                    smtp.starttls()
                smtp.login(self.config.smtp_username, self.config.smtp_password)
                smtp.send_message(message)
        except smtplib.SMTPException as exc:
            raise EmailDeliveryError(f"SMTP delivery failed: {exc}") from exc
        except OSError as exc:
            raise EmailDeliveryError(f"Could not reach the SMTP server: {exc}") from exc
