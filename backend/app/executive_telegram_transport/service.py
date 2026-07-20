from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TelegramTransportAssessment,
    TelegramTransportAssessmentCreate,
    TelegramTransportScores,
    TelegramTransportState,
    TelegramTransportStatusResponse,
)


class ExecutiveTelegramTransportService:
    def __init__(self) -> None:
        self._records: dict[UUID, TelegramTransportAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._message_transports: set[tuple[str, str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TelegramTransportAssessmentCreate) -> TelegramTransportAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        transport_key = (
            payload.workspace_id,
            payload.telegram_chat_id,
            payload.telegram_message_id,
            payload.transport_id,
        )
        if source_key in self._source_keys:
            raise ValueError("Duplicate Telegram transport source key")
        if transport_key in self._message_transports:
            raise ValueError("Duplicate Telegram message transport execution")

        policy = payload.policy
        attempts = sorted(payload.attempts, key=lambda item: item.attempt_number)
        latest = attempts[-1]
        session_isolated = bool(payload.session_reference) and payload.session_resolved and not payload.session_embedded
        type_allowed = (
            payload.transport_type == "telethon" and policy.allow_telethon_transport
        ) or (
            payload.transport_type == "bot-api" and policy.allow_bot_api_transport
        )
        valid = [
            item
            for item in attempts
            if item.connected
            and item.authenticated
            and item.media_retrieved
            and not item.timed_out
            and item.latency_ms <= policy.maximum_latency_ms
            and item.flood_wait_seconds == 0
            and item.reconnect_count <= policy.maximum_reconnects
            and (item.read_only_verified or not policy.require_read_only_transport)
        ]
        selected = valid[-1] if valid else None
        reasons: list[str] = []

        if not payload.risk_brain_clear:
            state, action = TelegramTransportState.blocked, "block-telegram-transport"
            reasons.append("Risk Brain blocks Telegram transport execution")
        elif payload.collector_state not in {"retrieval-queued", "media-ready", "dispatched"}:
            state, action = TelegramTransportState.blocked, "complete-telegram-collector-governance"
            reasons.append("Telegram collector has not authorized transport activity")
        elif not type_allowed:
            state, action = TelegramTransportState.blocked, "reject-disabled-telegram-transport"
            reasons.append("Requested Telegram transport type is disabled by policy")
        elif policy.require_isolated_session_reference and not session_isolated:
            state, action = TelegramTransportState.session_required, "resolve-isolated-telegram-session"
            reasons.append("Telegram transport requires an isolated resolved session reference")
        elif latest.flood_wait_seconds > 0:
            state, action = TelegramTransportState.flood_wait, "respect-telegram-flood-wait"
            reasons.append("Telegram rate limit requires a bounded wait before another request")
            if latest.flood_wait_seconds > policy.maximum_flood_wait_seconds:
                reasons.append("Flood-wait duration exceeds the automatic retry policy")
        elif selected is not None:
            state, action = TelegramTransportState.transport_ready, "accept-telegram-transport-result"
            reasons.append("Telegram transport passed connection, authentication and read-only gates")
        elif latest.retryable and latest.attempt_number < policy.maximum_attempts:
            state, action = TelegramTransportState.reconnect_required, "schedule-bounded-telegram-reconnect"
            reasons.append("Telegram transport failed temporarily and retry budget remains")
        else:
            state, action = TelegramTransportState.blocked, "fail-telegram-transport"
            reasons.append("Telegram transport failed permanently or exhausted retry budget")

        dispatchable = state == TelegramTransportState.transport_ready and selected is not None
        if dispatchable:
            state = TelegramTransportState.dispatched
            action = "dispatch-transport-result-to-v18-59"
            reasons.append("Read-only Telegram transport result is ready for collector governance")

        total = len(attempts)
        session_score = 100 if session_isolated else 0
        connection_score = round(100 * sum(item.connected for item in attempts) / total)
        authentication_score = round(100 * sum(item.authenticated for item in attempts) / total)
        reference = selected or latest
        latency_score = max(0, min(100, round(100 * (1 - reference.latency_ms / policy.maximum_latency_ms))))
        flood_ratio = reference.flood_wait_seconds / max(policy.maximum_flood_wait_seconds, 1)
        rate_limit_score = max(0, min(100, round(100 * (1 - flood_ratio))))
        confidence = round(
            (session_score + connection_score + authentication_score + latency_score + rate_limit_score) / 5
        )

        record = TelegramTransportAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            collector_assessment_id=payload.collector_assessment_id,
            transport_id=payload.transport_id,
            transport_type=payload.transport_type,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_message_id=payload.telegram_message_id,
            state=state,
            selected_attempt_number=selected.attempt_number if selected else None,
            dispatchable=dispatchable,
            target_module="executive-telegram-collector" if dispatchable else None,
            recommended_action=action,
            scores=TelegramTransportScores(
                session_isolation=session_score,
                connection_reliability=connection_score,
                authentication_quality=authentication_score,
                latency_quality=latency_score,
                rate_limit_safety=rate_limit_score,
                transport_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._message_transports.add(transport_key)
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                assessment_id=record.id,
                actor_id=payload.actor_id,
                action=action,
            )
        )
        return record

    def status(self, workspace_id: str) -> TelegramTransportStatusResponse:
        items = self.list_assessments(workspace_id)
        return TelegramTransportStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            latest_state=items[-1].state if items else None,
        )

    def list_assessments(self, workspace_id: str) -> list[TelegramTransportAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> TelegramTransportAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_telegram_transport_service = ExecutiveTelegramTransportService()
