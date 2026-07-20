import pytest

from app.executive_telegram_transport.models import (
    TelegramTransportAssessmentCreate,
    TelegramTransportState,
    TransportAttempt,
)
from app.executive_telegram_transport.service import ExecutiveTelegramTransportService


def attempt(**overrides):
    data = dict(
        attempt_number=1,
        connected=True,
        authenticated=True,
        read_only_verified=True,
        media_retrieved=True,
        latency_ms=500,
    )
    data.update(overrides)
    return TransportAttempt(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="tester",
        collector_assessment_id="collector-1",
        collector_state="retrieval-queued",
        transport_id="telethon-primary",
        transport_type="telethon",
        telegram_chat_id="chat-1",
        telegram_message_id="message-1",
        session_reference="secret://telegram/session",
        session_resolved=True,
        session_embedded=False,
        risk_brain_clear=True,
        attempts=[attempt()],
    )
    data.update(overrides)
    return TelegramTransportAssessmentCreate(**data)


def test_successful_read_only_transport_dispatches():
    result = ExecutiveTelegramTransportService().create(payload())
    assert result.state == TelegramTransportState.dispatched
    assert result.dispatchable is True
    assert result.target_module == "executive-telegram-collector"


def test_missing_isolated_session_is_blocked():
    result = ExecutiveTelegramTransportService().create(
        payload(session_reference=None, session_resolved=False)
    )
    assert result.state == TelegramTransportState.session_required
    assert result.dispatchable is False


def test_flood_wait_is_respected():
    result = ExecutiveTelegramTransportService().create(
        payload(attempts=[attempt(media_retrieved=False, flood_wait_seconds=60)])
    )
    assert result.state == TelegramTransportState.flood_wait
    assert result.dispatchable is False


def test_retryable_failure_requires_bounded_reconnect():
    result = ExecutiveTelegramTransportService().create(
        payload(attempts=[attempt(connected=False, authenticated=False, media_retrieved=False, retryable=True)])
    )
    assert result.state == TelegramTransportState.reconnect_required


def test_risk_brain_blocks_transport():
    result = ExecutiveTelegramTransportService().create(payload(risk_brain_clear=False))
    assert result.state == TelegramTransportState.blocked


def test_duplicate_and_workspace_isolation():
    service = ExecutiveTelegramTransportService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
