from __future__ import annotations

from uuid import UUID

from .models import (
    AdapterExecutionAssessment,
    AdapterExecutionAssessmentCreate,
    AdapterExecutionScores,
    AdapterExecutionState,
    AdapterExecutionStatusResponse,
    AuditRecord,
)


class ExecutiveVisionAdapterExecutionService:
    def __init__(self) -> None:
        self._records: dict[UUID, AdapterExecutionAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._image_keys: set[tuple[str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: AdapterExecutionAssessmentCreate) -> AdapterExecutionAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        image_key = (payload.workspace_id, payload.image_sha256, payload.adapter_id)
        if source_key in self._source_keys:
            raise ValueError("Duplicate vision adapter execution source key")
        if image_key in self._image_keys:
            raise ValueError("Duplicate image execution for adapter")

        policy = payload.policy
        attempts = sorted(payload.attempts, key=lambda item: item.attempt_number)
        valid_attempts = [
            item
            for item in attempts
            if item.success
            and not item.timed_out
            and item.latency_ms <= policy.maximum_latency_ms
            and item.response_bytes <= policy.maximum_response_bytes
            and item.estimated_cost_units <= policy.maximum_cost_units
            and item.extraction_confidence >= policy.minimum_extraction_confidence
            and (item.schema_valid or not policy.require_schema_valid)
            and (item.safety_clear or not policy.require_safety_clear)
        ]
        selected = valid_attempts[-1] if valid_attempts else None
        reasons: list[str] = []

        credential_isolated = bool(payload.credential_reference) and payload.credential_resolved and payload.request_payload_redacted
        if not payload.risk_brain_clear:
            state, action = AdapterExecutionState.blocked, "block-adapter-execution"
            reasons.append("Risk Brain blocks vision adapter execution")
        elif payload.routing_state != "dispatched":
            state, action = AdapterExecutionState.blocked, "complete-provider-routing"
            reasons.append("Provider routing has not dispatched this adapter")
        elif policy.require_isolated_credential_reference and not credential_isolated:
            state, action = AdapterExecutionState.credential_required, "resolve-isolated-credential-reference"
            reasons.append("Adapter credentials must be resolved through an isolated secret reference")
        elif selected is not None:
            state, action = AdapterExecutionState.completed, "accept-adapter-result"
            reasons.append("Adapter execution passed latency, cost, schema, safety and confidence policy")
        else:
            latest = attempts[-1]
            attempts_remaining = latest.attempt_number < policy.maximum_attempts
            if latest.retryable and attempts_remaining:
                state, action = AdapterExecutionState.retry_scheduled, "schedule-bounded-adapter-retry"
                reasons.append("Latest adapter failure is retryable and retry budget remains")
            else:
                state, action = AdapterExecutionState.failed, "fail-adapter-execution"
                reasons.append("Adapter execution exhausted retry budget or failed a non-retryable gate")

        dispatchable = state == AdapterExecutionState.completed and selected is not None
        if dispatchable:
            state = AdapterExecutionState.dispatched
            action = "dispatch-adapter-result-to-v18-56"
            reasons.append("Governed adapter result is ready for cross-provider consensus")

        total = len(attempts)
        successes = sum(item.success for item in attempts)
        credential_score = 100 if credential_isolated else 0
        reliability = round(100 * successes / total)
        reference = selected or attempts[-1]
        latency_quality = max(0, min(100, round(100 * (1 - reference.latency_ms / policy.maximum_latency_ms))))
        cost_efficiency = max(0, min(100, round(100 * (1 - reference.estimated_cost_units / policy.maximum_cost_units))))
        result_quality = reference.extraction_confidence if reference.schema_valid and reference.safety_clear else 0
        execution_confidence = round((credential_score + reliability + latency_quality + cost_efficiency + result_quality) / 5)

        record = AdapterExecutionAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            routing_assessment_id=payload.routing_assessment_id,
            provider_id=payload.provider_id,
            adapter_id=payload.adapter_id,
            image_sha256=payload.image_sha256,
            state=state,
            selected_attempt_number=selected.attempt_number if selected else None,
            dispatchable=dispatchable,
            target_module="executive-vision-adapter-consensus" if dispatchable else None,
            recommended_action=action,
            scores=AdapterExecutionScores(
                credential_isolation=credential_score,
                reliability=reliability,
                latency_quality=latency_quality,
                cost_efficiency=cost_efficiency,
                result_quality=result_quality,
                execution_confidence=execution_confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._image_keys.add(image_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def status(self, workspace_id: str) -> AdapterExecutionStatusResponse:
        items = self.list_assessments(workspace_id)
        return AdapterExecutionStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def list_assessments(self, workspace_id: str) -> list[AdapterExecutionAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> AdapterExecutionAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_vision_adapter_execution_service = ExecutiveVisionAdapterExecutionService()
