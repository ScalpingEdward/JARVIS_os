from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    VisionSignalAssessment,
    VisionSignalAssessmentCreate,
    VisionSignalScores,
    VisionSignalState,
    VisionSignalStatusResponse,
)


class ExecutiveTelegramChartVisionSignalIntelligenceService:
    def __init__(self) -> None:
        self._records: dict[UUID, VisionSignalAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._image_hashes: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: VisionSignalAssessmentCreate) -> VisionSignalAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        image_key = (payload.workspace_id, payload.image_sha256)
        if source_key in self._source_keys:
            raise ValueError("Duplicate Telegram vision source key")
        if image_key in self._image_hashes:
            raise ValueError("Duplicate Telegram chart image")

        e, policy = payload.extraction, payload.policy
        features = [name for name, enabled in e.ict.model_dump().items() if enabled]
        confluence_count = len(features)
        extraction_confidence = round((e.ocr_confidence + e.visual_confidence + e.chart_quality_score) / 3)
        ict_confluence = min(100, round(100 * confluence_count / max(policy.minimum_ict_confluences, 1)))

        complete_levels = all(value is not None for value in (e.entry_price, e.stop_loss, e.take_profit))
        level_integrity = 100 if complete_levels else 0
        risk_reward: float | None = None
        level_direction_valid = False
        if complete_levels and e.direction:
            entry, stop, target = e.entry_price, e.stop_loss, e.take_profit
            if e.direction == "long" and stop < entry < target:
                level_direction_valid = True
                risk_reward = round((target - entry) / (entry - stop), 2)
            elif e.direction == "short" and target < entry < stop:
                level_direction_valid = True
                risk_reward = round((entry - target) / (stop - entry), 2)
        if not level_direction_valid:
            level_integrity = 0
        risk_reward_quality = 0 if risk_reward is None else min(100, round(100 * risk_reward / policy.minimum_risk_reward))
        signal_confidence = round((extraction_confidence + ict_confluence + level_integrity + risk_reward_quality) / 4)
        reasons: list[str] = []

        required_context_missing = (
            (policy.require_symbol and not e.symbol)
            or (policy.require_timeframe and not e.timeframe)
            or (policy.require_levels and not complete_levels)
        )

        if not payload.risk_brain_clear:
            state, action = VisionSignalState.rejected, "reject-risk-blocked-signal"
            reasons.append("Risk Brain blocks this visual signal")
        elif e.chart_quality_score < policy.minimum_chart_quality_score:
            state, action = VisionSignalState.rejected, "request-clearer-chart-image"
            reasons.append("Chart image quality is below policy threshold")
        elif required_context_missing:
            state, action = VisionSignalState.context_required, "request-missing-chart-context"
            reasons.append("Symbol, timeframe or trade levels are incomplete")
        elif e.ocr_confidence < policy.minimum_ocr_confidence or e.visual_confidence < policy.minimum_visual_confidence:
            state, action = VisionSignalState.needs_review, "manually-review-vision-extraction"
            reasons.append("OCR or visual confidence is below policy threshold")
        elif not level_direction_valid:
            state, action = VisionSignalState.rejected, "reject-inconsistent-trade-levels"
            reasons.append("Entry, stop and target are inconsistent with direction")
        elif confluence_count < policy.minimum_ict_confluences or (risk_reward or 0) < policy.minimum_risk_reward:
            state, action = VisionSignalState.needs_review, "validate-ict-and-risk-reward"
            reasons.append("ICT confluence or risk-reward is below policy threshold")
        elif not payload.market_context_confirmed:
            state, action = VisionSignalState.validated, "confirm-live-market-context"
            reasons.append("Visual signal is valid but current market context is not confirmed")
        else:
            state, action = VisionSignalState.risk_eligible, "submit-to-risk-governance"
            reasons.append("Visual extraction, ICT structure and market context passed validation")

        trade_candidate = payload.human_approved and state == VisionSignalState.risk_eligible
        if state == VisionSignalState.risk_eligible and not payload.human_approved:
            reasons.append("Human approval is required before creating a trade candidate")

        record = VisionSignalAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_message_id=payload.telegram_message_id,
            image_sha256=payload.image_sha256,
            state=state,
            symbol=e.symbol,
            timeframe=e.timeframe,
            direction=e.direction,
            risk_reward=risk_reward,
            trade_candidate=trade_candidate,
            recommended_action=action,
            detected_features=features,
            scores=VisionSignalScores(
                extraction_confidence=extraction_confidence,
                ict_confluence=ict_confluence,
                level_integrity=level_integrity,
                risk_reward_quality=risk_reward_quality,
                signal_confidence=signal_confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._image_hashes.add(image_key)
        self._audit.append(AuditRecord(
            workspace_id=record.workspace_id,
            assessment_id=record.id,
            actor_id=record.actor_id,
            action=f"telegram-chart-vision:{record.state.value}",
        ))
        return record

    def status(self, workspace_id: str) -> VisionSignalStatusResponse:
        records = self.list_assessments(workspace_id)
        return VisionSignalStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            latest_state=records[-1].state if records else None,
        )

    def list_assessments(self, workspace_id: str) -> list[VisionSignalAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> VisionSignalAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_telegram_chart_vision_signal_intelligence_service = ExecutiveTelegramChartVisionSignalIntelligenceService()
