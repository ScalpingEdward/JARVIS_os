from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    TradeDirection,
    VisualSignalAssessment,
    VisualSignalAssessmentCreate,
    VisualSignalScores,
    VisualSignalState,
    VisualSignalStatusResponse,
)


class ExecutiveTelegramVisualSignalIntelligenceService:
    def __init__(self) -> None:
        self._records: dict[UUID, VisualSignalAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._image_hashes: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: VisualSignalAssessmentCreate) -> VisualSignalAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        image_key = (payload.workspace_id, payload.image_sha256)
        if source_key in self._source_keys:
            raise ValueError("Duplicate visual signal source key")
        if image_key in self._image_hashes:
            raise ValueError("Duplicate chart image")

        a, policy = payload.annotation, payload.policy
        risk_fields = [a.entry_low is not None or a.entry_high is not None, a.stop_loss is not None, bool(a.take_profits)]
        risk_completeness = round(sum(risk_fields) / len(risk_fields) * 100)
        signal_confidence = round(
            (
                payload.image_quality_score
                + payload.ocr_confidence
                + payload.direction_confidence
                + payload.structure_confidence
                + risk_completeness
            )
            / 5
        )
        reasons: list[str] = []

        missing_context = (policy.require_symbol and not a.symbol) or (policy.require_timeframe and not a.timeframe)
        missing_risk = policy.require_risk_levels and risk_completeness < 100
        weak_quality = payload.image_quality_score < policy.minimum_image_quality_score
        weak_ocr = payload.ocr_confidence < policy.minimum_ocr_confidence
        weak_direction = payload.direction_confidence < policy.minimum_direction_confidence
        weak_structure = payload.structure_confidence < policy.minimum_structure_confidence

        if not payload.risk_brain_clear:
            state, action = VisualSignalState.rejected, "reject-risk-brain-block"
            reasons.append("Risk Brain blocks the visual signal")
        elif weak_quality or a.direction == TradeDirection.unknown:
            state, action = VisualSignalState.rejected, "request-better-chart-image"
            reasons.append("Image quality or trade direction is insufficient")
        elif weak_ocr or missing_context:
            state, action = VisualSignalState.manual_review, "review-symbol-timeframe-and-text"
            reasons.append("OCR or chart context requires human verification")
        elif weak_direction or weak_structure:
            state, action = VisualSignalState.parsed, "validate-direction-and-ict-structure"
            reasons.append("Chart was parsed but directional or ICT confidence is below policy")
        elif missing_risk or signal_confidence < policy.minimum_signal_confidence:
            state, action = VisualSignalState.validated, "complete-risk-level-validation"
            reasons.append("Signal structure is valid but execution levels are incomplete or confidence is insufficient")
        else:
            state, action = VisualSignalState.actionable, "submit-to-strategy-review"
            reasons.append("Chart direction, ICT structure and risk levels satisfy visual signal policy")

        approved = payload.human_approved or not policy.require_human_approval
        usable = state in {VisualSignalState.validated, VisualSignalState.actionable} and approved
        if state == VisualSignalState.actionable and not approved:
            usable = False
            reasons.append("Human approval is required before strategy review")

        record = VisualSignalAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_message_id=payload.telegram_message_id,
            image_reference=payload.image_reference,
            image_sha256=payload.image_sha256,
            state=state,
            usable_for_strategy_review=usable,
            recommended_action=action,
            normalized_signal=a,
            scores=VisualSignalScores(
                image_quality=payload.image_quality_score,
                text_extraction=payload.ocr_confidence,
                direction_detection=payload.direction_confidence,
                ict_structure=payload.structure_confidence,
                risk_completeness=risk_completeness,
                signal_confidence=signal_confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._image_hashes.add(image_key)
        self._audit.append(
            AuditRecord(
                workspace_id=record.workspace_id,
                assessment_id=record.id,
                actor_id=record.actor_id,
                action=f"telegram-visual-signal:{record.state.value}",
            )
        )
        return record

    def status(self, workspace_id: str) -> VisualSignalStatusResponse:
        records = self.list_assessments(workspace_id)
        return VisualSignalStatusResponse(
            workspace_id=workspace_id,
            assessments=len(records),
            latest_state=records[-1].state if records else None,
        )

    def list_assessments(self, workspace_id: str) -> list[VisualSignalAssessment]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> VisualSignalAssessment | None:
        record = self._records.get(assessment_id)
        return record if record and record.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [record for record in self._audit if record.workspace_id == workspace_id]


executive_telegram_visual_signal_intelligence_service = ExecutiveTelegramVisualSignalIntelligenceService()
