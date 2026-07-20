from __future__ import annotations

from uuid import UUID

from .models import (
    AdapterRegistryAssessment,
    AdapterRegistryAssessmentCreate,
    AdapterRegistryScores,
    AdapterRegistryState,
    AdapterRegistryStatusResponse,
    AuditRecord,
)


class ExecutiveVisionAdapterRegistryService:
    def __init__(self) -> None:
        self._records: dict[UUID, AdapterRegistryAssessment] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._adapter_versions: set[tuple[str, str, str]] = set()
        self._audit: list[AuditRecord] = []

    def create(self, payload: AdapterRegistryAssessmentCreate) -> AdapterRegistryAssessment:
        source_key = (payload.workspace_id, payload.source_key)
        adapter_key = (payload.workspace_id, payload.adapter_id, payload.version)
        if source_key in self._source_keys:
            raise ValueError("Duplicate adapter registry source key")
        if adapter_key in self._adapter_versions:
            raise ValueError("Duplicate adapter version registration")

        policy, capability, health = payload.policy, payload.capability, payload.health
        reasons: list[str] = []
        capability_ok = (
            (capability.supports_chart_vision or not policy.require_chart_vision)
            and (capability.supports_structured_json or not policy.require_structured_json)
        )
        credentials_ok = health.credential_reference_configured or not policy.require_credentials
        reliability_ok = (
            health.success_rate_pct >= policy.minimum_success_rate_pct
            and health.consecutive_failures <= policy.maximum_consecutive_failures
        )
        latency_ok = health.p95_latency_ms <= policy.maximum_p95_latency_ms
        quota_ok = health.quota_remaining_pct >= policy.minimum_quota_remaining_pct
        cost_ok = (
            health.daily_cost_units <= policy.maximum_daily_cost_units
            and health.estimated_request_cost_units <= policy.maximum_request_cost_units
        )

        if not payload.risk_brain_clear:
            state, action = AdapterRegistryState.blocked, "block-adapter-registration"
            reasons.append("Risk Brain blocks adapter eligibility")
        elif not health.available or not capability_ok or not credentials_ok:
            state, action = AdapterRegistryState.unavailable, "remove-adapter-from-routing"
            reasons.append("Adapter is unavailable or lacks required capability or credentials")
        elif not reliability_ok or not latency_ok or not quota_ok or not cost_ok:
            state, action = AdapterRegistryState.constrained, "limit-or-deprioritize-adapter"
            reasons.append("Adapter exceeds health, latency, quota or cost policy")
        elif payload.human_preferred:
            state, action = AdapterRegistryState.preferred, "publish-preferred-adapter"
            reasons.append("Adapter passes policy and is human-designated as preferred")
        else:
            state, action = AdapterRegistryState.eligible, "publish-eligible-adapter"
            reasons.append("Adapter passes capability, health, quota and cost policy")

        routable = state in {AdapterRegistryState.eligible, AdapterRegistryState.preferred}
        executable = routable and credentials_ok
        capability_fit = 100 if capability_ok else 0
        reliability = round(health.success_rate_pct)
        latency_quality = max(0, min(100, round(100 * (1 - health.p95_latency_ms / policy.maximum_p95_latency_ms))))
        quota_headroom = round(health.quota_remaining_pct)
        request_ratio = health.estimated_request_cost_units / policy.maximum_request_cost_units
        daily_ratio = health.daily_cost_units / policy.maximum_daily_cost_units
        cost_efficiency = max(0, min(100, round(100 * (1 - max(request_ratio, daily_ratio)))))
        registry_confidence = round((capability_fit + reliability + latency_quality + quota_headroom + cost_efficiency) / 5)

        record = AdapterRegistryAssessment(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            actor_id=payload.actor_id,
            provider_id=payload.provider_id,
            adapter_id=payload.adapter_id,
            version=payload.version,
            state=state,
            routable=routable,
            executable=executable,
            recommended_action=action,
            scores=AdapterRegistryScores(
                capability_fit=capability_fit,
                reliability=reliability,
                latency_quality=latency_quality,
                quota_headroom=quota_headroom,
                cost_efficiency=cost_efficiency,
                registry_confidence=registry_confidence,
            ),
            reasons=reasons,
        )
        self._records[record.id] = record
        self._source_keys.add(source_key)
        self._adapter_versions.add(adapter_key)
        self._audit.append(AuditRecord(workspace_id=payload.workspace_id, assessment_id=record.id, actor_id=payload.actor_id, action=action))
        return record

    def status(self, workspace_id: str) -> AdapterRegistryStatusResponse:
        items = self.list_assessments(workspace_id)
        return AdapterRegistryStatusResponse(workspace_id=workspace_id, assessments=len(items), latest_state=items[-1].state if items else None)

    def list_assessments(self, workspace_id: str) -> list[AdapterRegistryAssessment]:
        return [item for item in self._records.values() if item.workspace_id == workspace_id]

    def get(self, assessment_id: UUID, workspace_id: str) -> AdapterRegistryAssessment | None:
        item = self._records.get(assessment_id)
        return item if item and item.workspace_id == workspace_id else None

    def audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self._audit if item.workspace_id == workspace_id]


executive_vision_adapter_registry_service = ExecutiveVisionAdapterRegistryService()
