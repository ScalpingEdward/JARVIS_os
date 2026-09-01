from __future__ import annotations

import smtplib

import pytest

from app.notification_hub.email_delivery import EmailDeliveryConfig, EmailDeliveryError, SmtpEmailDeliveryClient


class FakeSmtp:
    """Stands in for smtplib.SMTP as a context manager -- a real network
    client can't be exercised with httpx.MockTransport, so this fake
    tracks the same calls a real one would receive."""

    instances: list["FakeSmtp"] = []

    def __init__(self, raise_on=None):
        self.started_tls = False
        self.login_call = None
        self.sent_message = None
        self.raise_on = raise_on
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        if self.raise_on == "starttls":
            raise smtplib.SMTPException("STARTTLS failed")
        self.started_tls = True

    def login(self, username, password):
        if self.raise_on == "login":
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.login_call = (username, password)

    def send_message(self, message):
        if self.raise_on == "send":
            raise smtplib.SMTPException("send failed")
        self.sent_message = message


def _full_config(**overrides):
    base = dict(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="bot@example.com",
        smtp_password="app-password",
        from_address="bot@example.com",
        to_address="brano@example.com",
    )
    base.update(overrides)
    return EmailDeliveryConfig(**base)


def test_send_fails_closed_when_settings_are_missing():
    client = SmtpEmailDeliveryClient(config=EmailDeliveryConfig())
    with pytest.raises(EmailDeliveryError, match="Missing required email settings"):
        client.send("Subject", "Body")


def test_send_reports_every_missing_setting():
    client = SmtpEmailDeliveryClient(config=EmailDeliveryConfig(smtp_host="smtp.example.com"))
    with pytest.raises(EmailDeliveryError) as exc_info:
        client.send("Subject", "Body")
    message = str(exc_info.value)
    assert "SMTP_USERNAME" in message
    assert "NOTIFICATION_EMAIL_TO" in message


def test_send_delivers_via_the_real_smtp_flow():
    FakeSmtp.instances.clear()
    client = SmtpEmailDeliveryClient(config=_full_config(), smtp_factory=lambda: FakeSmtp())
    client.send("Post ready", "A hero post is waiting for review.")

    smtp = FakeSmtp.instances[-1]
    assert smtp.started_tls is True
    assert smtp.login_call == ("bot@example.com", "app-password")
    assert smtp.sent_message["Subject"] == "Post ready"
    assert smtp.sent_message["From"] == "bot@example.com"
    assert smtp.sent_message["To"] == "brano@example.com"
    assert "hero post" in smtp.sent_message.get_content()


def test_send_raises_on_login_failure():
    client = SmtpEmailDeliveryClient(config=_full_config(), smtp_factory=lambda: FakeSmtp(raise_on="login"))
    with pytest.raises(EmailDeliveryError, match="SMTP delivery failed"):
        client.send("Subject", "Body")


def test_send_raises_on_send_failure():
    client = SmtpEmailDeliveryClient(config=_full_config(), smtp_factory=lambda: FakeSmtp(raise_on="send"))
    with pytest.raises(EmailDeliveryError, match="SMTP delivery failed"):
        client.send("Subject", "Body")


def test_send_skips_starttls_when_disabled():
    FakeSmtp.instances.clear()
    client = SmtpEmailDeliveryClient(config=_full_config(use_starttls=False), smtp_factory=lambda: FakeSmtp())
    client.send("Subject", "Body")
    assert FakeSmtp.instances[-1].started_tls is False
