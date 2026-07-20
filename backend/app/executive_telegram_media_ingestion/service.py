from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    IngestionScores,
    IngestionState,
    IngestionStatusResponse,
    TelegramMediaIngestion,
    TelegramMediaIngestionCreate,
)


class ExecutiveTelegramMediaIngestionService:
    def __init__(self) -> None:
        self._records: dict[UUID, TelegramMediaIngestion] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._image_hashes: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: TelegramMediaIngestionCreate) -> TelegramMediaIngestion:
        source_key = (payload.workspace_id, payload.source_key)
        image_key = (payload.workspace_id, payload.image_sha256)
        if source_key in self._source_keys:
            raise ValueError("Duplicate Telegram media source key")
        if image_key in self._image_hashes:
            raise ValueError("Duplicate Telegram media image")

        policy = payload.policy
        mime_allowed = payload.mime_type in policy.allowed_mime_types
        size_allowed = payload.size_bytes <= policy.maximum_size_bytes
        readable = payload.width >= policy.minimum_width and payload.height >= policy.minimum_height
        context_present = bool((payload.caption or "").strip())
        approved = payload.human_approved or not policy.require_human_approval

        source_trust = 100 if payload.chat_allowlisted else 25
        media_integrity = 100 if payload.malware_scan_clear and mime_allowed and size_allowed else 0
        chart_readability = min(100, round(50 * payload.width / policy.minimum_width + 50 * payload.height / policy.minimum_height))
        dispatch_readiness = round((source_trust + media_integrity + chart_readability + (100 if payload.vision_provider_available else 0)) / 4)
        reasons: list[str] = []

        if not payload.malware_scan_clear or not mime_allowed:
            state, action = IngestionState.rejected, "reject-unsafe-or-unsupported-media"
            reasons.append("Media integrity or MIME policy failed")
        elif not size_allowed or not readable:
            state, action = IngestionState.quarantined, "request-readable-chart-image"
            reasons.append("Image size or chart resolution is outside policy")
        elif policy.require_allowlisted_chat and not payload.chat_allowlisted:
            state, action = IngestionState.quarantined, "review-telegram-source"
            reasons.append("Telegram chat is not allowlisted")
        elif policy.require_caption_or_chart_context and not context_present:
            state, action = IngestionState.accepted, "request-chart-context"
            reasons.append("Media is accepted but caption or chart context is missing")
        elif not payload.vision_provider_available:
            state, action = IngestionState.vision_ready, "queue-until-vision-provider-recovers"
            reasons.append("Media is ready but the configured vision provider is unavailable")
        elif not approved:
            state, action = IngestionState.vision_ready, "await-human-dispatch-approval"
            reasons.append("Human approval is required before vision dispatch")
        else:
            state, action = IngestionState.dispatched, "dispatch-to-v18-53-chart-vision"
            reasons.append("Telegram media passed ingestion and dispatch governance")

        dispatchable = state == IngestionState.dispatched
        target_module = "executive-telegram-chart-vision-signal-intelligence" if dispatchable else None
        record = TelegramMediaIngestion(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_message_id=payload.telegram_message_id,
            media_reference=payload.media_reference,
            image_sha256=payload.image_sha256,
            state=state,
            dispatchable=dispatchable,
            target_module=target_module,
            recommended_action=action,
            scores=IngestionScores(
                source_trust=source_trust,
                media_integrity=media_integrity,
                chart_readability=chart_readability,
                dispatch_readiness=dispatch_readiness,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._image_hashes.add(image_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, ingestion_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def status(self, workspace_id: str) -> IngestionStatusResponse:
        items = self.list_ingestions(workspace_id)
        return IngestionStatusResponse(workspace_id=workspace_id, ingestions=len(items), latest_state=items[-1].state if items else None)

    def list_ingestions(self, workspace_id: str) -> list[TelegramMediaIngestion]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, ingestion_id: UUID, workspace_id: str) -> TelegramMediaIngestion | None:
        item = self._records.get(ingestion_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_telegram_media_ingestion_service = ExecutiveTelegramMediaIngestionService()
