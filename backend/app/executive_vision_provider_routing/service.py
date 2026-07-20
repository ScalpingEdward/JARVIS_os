from __future__ import annotations

from uuid import UUID

from .models import (
    AuditRecord,
    ProviderObservation,
    VisionRoutingAssessment,
    VisionRoutingAssessmentCreate,
    VisionRoutingScores,
    VisionRoutingState,
    VisionRoutingStatusResponse,
)


class ExecutiveVisionProviderRoutingService:
    def __init__(self) -> None:
        self._records: dict[UUID, VisionRoutingAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._image_hashes: set[tuple[str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: VisionRoutingAssessmentCreate) -> VisionRoutingAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        image_key = (payload.workspace_id, payload.image_sha256)
        if source_key in self._source_keys:
            raise ValueError("Duplicate vision routing source key")
        if image_key in self._image_hashes:
            raise ValueError("Duplicate vision routing image")

        policy = payload.policy
        preferred = next((p for p in payload.providers if p.provider_id == policy.preferred_provider_id), None)
        eligible = [p for p in payload.providers if self._eligible(p, policy)]
        selected: ProviderObservation | None = None
        fallback_used = False
        reasons: list[str] = []

        if not payload.risk_brain_clear:
            state, action = VisionRoutingState.blocked, "block-vision-routing"
            reasons.append("Risk Brain blocks vision-provider routing")
        elif preferred and self._eligible(preferred, policy):
            selected = preferred
            state, action = VisionRoutingState.extracted, "accept-primary-extraction"
            reasons.append("Preferred provider passed extraction policy")
        elif eligible and policy.allow_fallback:
            selected = max(eligible, key=lambda item: (item.extraction_confidence, -item.latency_ms, -item.estimated_cost_units))
            fallback_used = True
            approved = payload.human_approved or not policy.require_human_approval_for_fallback
            if approved:
                state, action = VisionRoutingState.extracted, "accept-fallback-extraction"
                reasons.append("Fallback provider passed extraction policy")
            else:
                state, action = VisionRoutingState.fallback_required, "approve-fallback-provider"
                reasons.append("Fallback provider requires human approval")
        elif any(p.available and not p.timed_out for p in payload.providers):
            state, action = VisionRoutingState.fallback_required, "retry-or-route-alternate-provider"
            reasons.append("Available providers failed confidence, schema, latency, cost or error gates")
        else:
            state, action = VisionRoutingState.queued, "queue-until-provider-recovers"
            reasons.append("No vision provider is currently available")

        dispatchable = state == VisionRoutingState.extracted and selected is not None
        if dispatchable:
            state = VisionRoutingState.dispatched
            action = "dispatch-extraction-to-v18-53"
            reasons.append("Governed extraction is ready for chart-signal validation")

        observations = payload.providers
        availability = round(100 * sum(p.available and not p.timed_out for p in observations) / len(observations))
        extraction_quality = selected.extraction_confidence if selected else max((p.extraction_confidence for p in observations), default=0)
        latency_quality = 0 if not selected else max(0, min(100, round(100 * (1 - selected.latency_ms / policy.maximum_latency_ms))))
        cost_efficiency = 0 if not selected else max(0, min(100, round(100 * (1 - selected.estimated_cost_units / policy.maximum_cost_units))))
        dispatch_confidence = round((availability + extraction_quality + latency_quality + cost_efficiency) / 4)

        record = VisionRoutingAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            ingestion_id=payload.ingestion_id,
            image_sha256=payload.image_sha256,
            state=state,
            selected_provider_id=selected.provider_id if selected else None,
            fallback_used=fallback_used,
            dispatchable=dispatchable,
            target_module=payload.target_module if dispatchable else None,
            recommended_action=action,
            scores=VisionRoutingScores(
                availability=availability,
                extraction_quality=extraction_quality,
                latency_quality=latency_quality,
                cost_efficiency=cost_efficiency,
                dispatch_confidence=dispatch_confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._image_hashes.add(image_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    @staticmethod
    def _eligible(provider: ProviderObservation, policy) -> bool:
        return (
            provider.available
            and not provider.timed_out
            and provider.safety_clear
            and provider.extraction_confidence >= policy.minimum_extraction_confidence
            and provider.latency_ms <= policy.maximum_latency_ms
            and provider.estimated_cost_units <= policy.maximum_cost_units
            and provider.error_count <= policy.maximum_provider_errors
            and (provider.schema_valid or not policy.require_schema_valid)
        )

    def status(self, workspace_id: str) -> VisionRoutingStatusResponse:
        items = self.list_assessments(workspace_id)
        return VisionRoutingStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def list_assessments(self, workspace_id: str) -> list[VisionRoutingAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> VisionRoutingAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_vision_provider_routing_service = ExecutiveVisionProviderRoutingService()
