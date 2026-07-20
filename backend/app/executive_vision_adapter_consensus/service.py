from __future__ import annotations

from collections import Counter
from statistics import median
from uuid import UUID

from .models import (
    AdapterExtraction,
    AuditRecord,
    ConsensusAssessment,
    ConsensusAssessmentCreate,
    ConsensusScores,
    ConsensusState,
    ConsensusStatusResponse,
    NormalizedExtraction,
)


class ExecutiveVisionAdapterConsensusService:
    def __init__(self) -> None:
        self._records: dict[UUID, ConsensusAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._image_hashes: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: ConsensusAssessmentCreate) -> ConsensusAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        image_key = (payload.workspace_id, payload.image_sha256)
        if source_key in self._source_keys:
            raise ValueError("Duplicate vision consensus source key")
        if image_key in self._image_hashes:
            raise ValueError("Duplicate vision consensus image")

        policy = payload.policy
        eligible = [
            item
            for item in payload.extractions
            if item.success
            and item.schema_valid
            and item.safety_clear
            and item.confidence >= policy.minimum_adapter_confidence
        ]
        successful = [item for item in payload.extractions if item.success]
        schema_valid = [item for item in successful if item.schema_valid and item.safety_clear]
        reasons: list[str] = []
        normalized: NormalizedExtraction | None = None

        adapter_success = round(100 * len(successful) / len(payload.extractions))
        schema_quality = round(100 * len(schema_valid) / len(payload.extractions))
        directional_agreement = 0
        level_agreement = 0

        if not payload.risk_brain_clear:
            state, action = ConsensusState.blocked, "block-vision-normalization"
            reasons.append("Risk Brain blocks adapter-result normalization")
        elif payload.routing_state != "dispatched":
            state, action = ConsensusState.blocked, "complete-provider-routing"
            reasons.append("Provider routing has not produced a dispatched extraction")
        elif not eligible:
            state, action = ConsensusState.retry_required, "retry-vision-adapter-invocation"
            reasons.append("No adapter result passed success, schema, safety and confidence gates")
        else:
            keys = [(item.symbol, item.timeframe, item.direction) for item in eligible]
            winning_key, winning_count = Counter(keys).most_common(1)[0]
            agreeing = [item for item in eligible if (item.symbol, item.timeframe, item.direction) == winning_key]
            directional_agreement = round(100 * winning_count / len(eligible))

            minimum = policy.minimum_agreeing_adapters if policy.require_consensus_for_multiple_results else 1
            single_override = (
                len(eligible) == 1
                and policy.allow_single_adapter_with_human_approval
                and payload.human_approved
            )
            context_missing = (
                (policy.require_symbol and not winning_key[0])
                or (policy.require_timeframe and not winning_key[1])
                or winning_key[2] == "unknown"
            )

            if winning_count < minimum and not single_override:
                state, action = ConsensusState.disagreement, "review-cross-provider-disagreement"
                if len(eligible) == 1:
                    reasons.append("A single adapter requires explicit human approval before normalization")
                else:
                    reasons.append("Vision providers disagree on symbol, timeframe or trade direction")
            elif context_missing:
                state, action = ConsensusState.disagreement, "review-incomplete-normalized-context"
                reasons.append("Consensus lacks required symbol, timeframe or direction")
            else:
                entries = [item.entry_price for item in agreeing if item.entry_price is not None]
                stops = [item.stop_loss for item in agreeing if item.stop_loss is not None]
                levels_complete = bool(entries and stops and all(item.take_profits for item in agreeing))
                entry_deviation = 0.0
                if len(entries) > 1:
                    midpoint = median(entries)
                    entry_deviation = 0 if midpoint == 0 else (max(entries) - min(entries)) / midpoint * 10_000
                level_agreement = max(0, min(100, round(100 * (1 - entry_deviation / max(policy.maximum_entry_deviation_bps, 0.01)))))

                if policy.require_trade_levels and not levels_complete:
                    state, action = ConsensusState.disagreement, "review-incomplete-trade-levels"
                    reasons.append("Adapters did not provide complete entry, stop and take-profit levels")
                elif entry_deviation > policy.maximum_entry_deviation_bps:
                    state, action = ConsensusState.disagreement, "review-price-level-disagreement"
                    reasons.append("Adapter entry prices exceed the permitted deviation")
                else:
                    best = max(agreeing, key=lambda item: item.confidence)
                    ict_features = sorted({feature for item in agreeing for feature in item.ict_features})
                    normalized = NormalizedExtraction(
                        symbol=winning_key[0],
                        timeframe=winning_key[1],
                        direction=winning_key[2],
                        entry_price=round(median(entries), 8) if entries else None,
                        stop_loss=round(median(stops), 8) if stops else None,
                        take_profits=best.take_profits,
                        ict_features=ict_features,
                        agreeing_provider_ids=[item.provider_id for item in agreeing],
                    )
                    state, action = ConsensusState.normalized, "normalize-adapter-extractions"
                    reasons.append("Adapter outputs satisfy consensus and normalization policy")

        dispatchable = state == ConsensusState.normalized and normalized is not None
        if dispatchable:
            state = ConsensusState.dispatched
            action = "dispatch-normalized-extraction-to-v18-53"
            reasons.append("Normalized chart extraction is ready for ICT signal validation")

        normalization_confidence = round(
            (adapter_success + schema_quality + directional_agreement + level_agreement) / 4
        )
        record = ConsensusAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            routing_assessment_id=payload.routing_assessment_id,
            image_sha256=payload.image_sha256,
            state=state,
            dispatchable=dispatchable,
            target_module="executive-telegram-chart-vision-signal-intelligence" if dispatchable else None,
            recommended_action=action,
            normalized_extraction=normalized,
            scores=ConsensusScores(
                adapter_success=adapter_success,
                schema_quality=schema_quality,
                directional_agreement=directional_agreement,
                level_agreement=level_agreement,
                normalization_confidence=normalization_confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._image_hashes.add(image_key)
        self._audit.append(
            AuditRecord(
                workspace_id=payload.workspace_id,
                assessment_id=record.id,
                actor_id=payload.actor_id,
                action=action,
            )
        )
        return record

    def status(self, workspace_id: str) -> ConsensusStatusResponse:
        items = self.list_assessments(workspace_id)
        return ConsensusStatusResponse(
            workspace_id=workspace_id,
            assessments=len(items),
            latest_state=items[-1].state if items else None,
        )

    def list_assessments(self, workspace_id: str) -> list[ConsensusAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> ConsensusAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_vision_adapter_consensus_service = ExecutiveVisionAdapterConsensusService()
