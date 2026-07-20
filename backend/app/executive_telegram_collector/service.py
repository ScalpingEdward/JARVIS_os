from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TelegramCollectorAssessment,
    TelegramCollectorAssessmentCreate,
    TelegramCollectorScores,
    TelegramCollectorState,
    TelegramCollectorStatusResponse,
)


class ExecutiveTelegramCollectorService:
    def __init__(self) -> None:
        self._records: dict[UUID, TelegramCollectorAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._message_keys: set[tuple[str, str, str]] = set()
        self._image_hashes: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TelegramCollectorAssessmentCreate) -> TelegramCollectorAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        message_key = (payload.workspace_id, payload.telegram_chat_id, payload.telegram_message_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate Telegram collector source key")
        if message_key in self._message_keys:
            raise ValueError("Duplicate Telegram message collection")
        if payload.image_sha256 and (payload.workspace_id, payload.image_sha256) in self._image_hashes:
            raise ValueError("Duplicate Telegram collector image")

        policy = payload.policy
        session_isolated = bool(payload.session_reference) and payload.session_resolved and not payload.session_file_embedded
        source_trusted = payload.source_allowlisted or not policy.require_allowlisted_source
        freshness_ok = payload.message_age_seconds <= policy.maximum_message_age_seconds
        client_safe = payload.read_only_client or not policy.require_read_only_client
        mime_ok = payload.mime_type in policy.allowed_mime_types if payload.mime_type else False
        size_ok = 0 < payload.size_bytes <= policy.maximum_media_bytes
        dimensions_ok = payload.width > 0 and payload.height > 0
        media_valid = payload.media_present and mime_ok and size_ok and dimensions_ok
        retrieval_complete = payload.retrieval_success and bool(payload.media_reference) and bool(payload.image_sha256)
        reasons: list[str] = []

        if not payload.risk_brain_clear:
            state, action = TelegramCollectorState.blocked, "block-telegram-collection"
            reasons.append("Risk Brain blocks Telegram collector activity")
        elif policy.require_isolated_session_reference and not session_isolated:
            state, action = TelegramCollectorState.session_required, "resolve-isolated-telegram-session"
            reasons.append("Telegram session must use an isolated reference and must not be embedded")
        elif not source_trusted or not client_safe:
            state, action = TelegramCollectorState.source_rejected, "reject-telegram-source-or-client"
            reasons.append("Telegram source is not allowlisted or collector is not read-only")
        elif not freshness_ok:
            state, action = TelegramCollectorState.source_rejected, "reject-stale-telegram-message"
            reasons.append("Telegram message exceeds the permitted collection age")
        elif retrieval_complete and media_valid:
            state, action = TelegramCollectorState.media_ready, "accept-retrieved-telegram-media"
            reasons.append("Telegram media passed session, source, freshness and integrity governance")
        elif payload.retryable_failure and payload.retrieval_attempts < policy.maximum_retrieval_attempts:
            state, action = TelegramCollectorState.retrieval_queued, "schedule-bounded-media-retrieval-retry"
            reasons.append("Media retrieval failed temporarily and retry budget remains")
        else:
            state, action = TelegramCollectorState.source_rejected, "reject-unusable-telegram-media"
            reasons.append("Telegram message has no acceptable retrievable chart media")

        dispatchable = state == TelegramCollectorState.media_ready
        if dispatchable:
            state = TelegramCollectorState.dispatched
            action = "dispatch-telegram-media-to-v18-54"
            reasons.append("Collected media is ready for Telegram media-ingestion governance")

        session_score = 100 if session_isolated else 0
        source_score = 100 if source_trusted and client_safe else 0
        freshness_score = max(0, min(100, round(100 * (1 - payload.message_age_seconds / policy.maximum_message_age_seconds))))
        media_score = 100 if media_valid else 0
        retrieval_score = 100 if retrieval_complete else max(0, round(100 * (1 - payload.retrieval_attempts / policy.maximum_retrieval_attempts)))
        confidence = round((session_score + source_score + freshness_score + media_score + retrieval_score) / 5)

        record = TelegramCollectorAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            collector_id=payload.collector_id,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_message_id=payload.telegram_message_id,
            state=state,
            dispatchable=dispatchable,
            target_module="executive-telegram-media-ingestion" if dispatchable else None,
            media_reference=payload.media_reference if dispatchable else None,
            image_sha256=payload.image_sha256 if dispatchable else None,
            recommended_action=action,
            scores=TelegramCollectorScores(
                session_isolation=session_score,
                source_trust=source_score,
                freshness=freshness_score,
                media_integrity=media_score,
                retrieval_reliability=retrieval_score,
                collector_confidence=confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._message_keys.add(message_key)
        if payload.image_sha256:
            self._image_hashes.add((payload.workspace_id, payload.image_sha256))
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def status(self, workspace_id: str) -> TelegramCollectorStatusResponse:
        items = self.list_assessments(workspace_id)
        return TelegramCollectorStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def list_assessments(self, workspace_id: str) -> list[TelegramCollectorAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> TelegramCollectorAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_telegram_collector_service = ExecutiveTelegramCollectorService()
