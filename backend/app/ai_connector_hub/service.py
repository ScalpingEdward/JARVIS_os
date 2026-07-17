from datetime import datetime, timezone
from uuid import UUID

from .models import (
    AIConnectorHubStatus,
    ModelProfile,
    ProviderMutation,
    ProviderRecord,
    ProviderRegister,
    ProviderState,
    RequestState,
    RoutingCandidate,
    RoutingDecision,
    RoutingRequest,
    RoutingStrategy,
    UsageRecord,
    UsageRecordCreate,
)


class AIConnectorHubService:
    def __init__(self) -> None:
        self._providers: dict[UUID, ProviderRecord] = {}
        self._decisions: dict[UUID, RoutingDecision] = {}
        self._usage: dict[UUID, UsageRecord] = {}

    def status(self) -> AIConnectorHubStatus:
        providers = list(self._providers.values())
        return AIConnectorHubStatus(
            registered_providers=len(providers),
            active_providers=sum(item.state == ProviderState.ACTIVE for item in providers),
            degraded_providers=sum(item.state == ProviderState.DEGRADED for item in providers),
            available_models=sum(len([model for model in item.models if model.enabled]) for item in providers),
            routing_decisions=len(self._decisions),
            usage_records=len(self._usage),
            estimated_total_spend=round(sum(item.actual_cost for item in self._usage.values()), 8),
        )

    def register(self, payload: ProviderRegister) -> ProviderRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.provider_key == payload.provider_key
            for item in self._providers.values()
        )
        if duplicate:
            raise ValueError("provider key already exists in workspace")
        model_keys = [model.model_key for model in payload.models]
        if len(model_keys) != len(set(model_keys)):
            raise ValueError("model keys must be unique inside a provider")
        record = ProviderRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            provider_key=payload.provider_key,
            provider_type=payload.provider_type,
            display_name=payload.display_name.strip(),
            models=payload.models,
            monthly_budget=payload.monthly_budget,
            local_provider=payload.local_provider,
            supports_dry_run=payload.supports_dry_run,
        )
        self._providers[record.id] = record
        return record

    def list_providers(self, workspace_id: str) -> list[ProviderRecord]:
        return sorted(
            [item for item in self._providers.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def get(self, provider_id: UUID, workspace_id: str) -> ProviderRecord | None:
        provider = self._providers.get(provider_id)
        if provider is None or provider.workspace_id != workspace_id:
            return None
        return provider

    def activate(
        self,
        provider_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: ProviderMutation,
    ) -> ProviderRecord | None:
        provider = self._owned(provider_id, workspace_id, requester_id)
        if provider is None:
            return None
        if not provider.models:
            provider.state = ProviderState.QUARANTINED
            provider.health_message = "No models configured"
        else:
            provider.state = ProviderState.ACTIVE
            provider.health_message = payload.reason or "Active"
        provider.updated_at = self._now()
        return provider

    def disable(
        self,
        provider_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: ProviderMutation,
    ) -> ProviderRecord | None:
        provider = self._owned(provider_id, workspace_id, requester_id)
        if provider is None:
            return None
        provider.state = ProviderState.DISABLED
        provider.health_message = payload.reason or "Disabled"
        provider.updated_at = self._now()
        return provider

    def heartbeat(self, provider_id: UUID, workspace_id: str, healthy: bool, message: str) -> ProviderRecord | None:
        provider = self.get(provider_id, workspace_id)
        if provider is None:
            return None
        provider.last_heartbeat_at = self._now()
        if provider.state not in {ProviderState.DISABLED, ProviderState.QUARANTINED}:
            provider.state = ProviderState.ACTIVE if healthy else ProviderState.DEGRADED
        provider.health_message = message or ("Healthy" if healthy else "Degraded")
        provider.updated_at = self._now()
        return provider

    def route(self, payload: RoutingRequest) -> RoutingDecision:
        candidates: list[RoutingCandidate] = []
        for provider in self._providers.values():
            if provider.workspace_id != payload.workspace_id or provider.state != ProviderState.ACTIVE:
                continue
            if provider.provider_key in payload.excluded_provider_keys:
                continue
            if payload.require_local and not provider.local_provider:
                continue
            for model in provider.models:
                candidate = self._candidate(provider, model, payload)
                if candidate is not None:
                    candidates.append(candidate)

        candidates.sort(key=lambda item: item.score, reverse=True)
        selected = candidates[0] if candidates else None
        blocked_reason = None
        state = RequestState.ROUTED
        if selected is None:
            state = RequestState.BLOCKED
            blocked_reason = "No active compatible model within policy and budget"
        decision = RoutingDecision(
            workspace_id=payload.workspace_id,
            requester_id=payload.requester_id,
            capability=payload.capability,
            strategy=payload.strategy,
            state=state,
            selected=selected,
            candidates=candidates[:20],
            blocked_reason=blocked_reason,
        )
        self._decisions[decision.id] = decision
        return decision

    def list_decisions(self, workspace_id: str) -> list[RoutingDecision]:
        return [item for item in self._decisions.values() if item.workspace_id == workspace_id]

    def record_usage(self, payload: UsageRecordCreate) -> UsageRecord | None:
        provider = self.get(payload.provider_id, payload.workspace_id)
        if provider is None:
            return None
        if not any(model.model_key == payload.model_key for model in provider.models):
            return None
        record = UsageRecord(
            workspace_id=payload.workspace_id,
            provider_id=payload.provider_id,
            model_key=payload.model_key,
            input_tokens=payload.input_tokens,
            output_tokens=payload.output_tokens,
            actual_cost=payload.actual_cost,
            success=payload.success,
            dry_run=payload.dry_run,
        )
        self._usage[record.id] = record
        provider.request_count += 1
        provider.failure_count += int(not payload.success)
        provider.current_month_spend = round(provider.current_month_spend + payload.actual_cost, 8)
        if provider.monthly_budget > 0 and provider.current_month_spend >= provider.monthly_budget:
            provider.state = ProviderState.DEGRADED
            provider.health_message = "Monthly budget reached"
        provider.updated_at = self._now()
        return record

    def list_usage(self, workspace_id: str) -> list[UsageRecord]:
        return [item for item in self._usage.values() if item.workspace_id == workspace_id]

    def _candidate(
        self,
        provider: ProviderRecord,
        model: ModelProfile,
        payload: RoutingRequest,
    ) -> RoutingCandidate | None:
        if not model.enabled or payload.capability not in model.capabilities:
            return None
        estimated_cost = round(
            (payload.estimated_input_tokens / 1_000_000) * model.input_cost_per_million
            + (payload.estimated_output_tokens / 1_000_000) * model.output_cost_per_million,
            8,
        )
        remaining_budget = max(provider.monthly_budget - provider.current_month_spend, 0.0)
        if estimated_cost > payload.maximum_estimated_cost:
            return None
        if provider.monthly_budget > 0 and estimated_cost > remaining_budget:
            return None

        preferred = provider.provider_key in payload.preferred_provider_keys
        cost_score = 1 / (1 + estimated_cost)
        local_score = 1.0 if provider.local_provider else 0.0
        if payload.strategy == RoutingStrategy.LOWEST_COST:
            score = cost_score
        elif payload.strategy == RoutingStrategy.LOWEST_LATENCY:
            score = model.latency_score
        elif payload.strategy == RoutingStrategy.HIGHEST_QUALITY:
            score = model.quality_score
        elif payload.strategy == RoutingStrategy.LOCAL_FIRST:
            score = 0.7 * local_score + 0.2 * model.quality_score + 0.1 * cost_score
        else:
            score = 0.4 * model.quality_score + 0.3 * model.latency_score + 0.3 * cost_score
        if preferred:
            score += 0.15
        reasons = [
            f"capability:{payload.capability}",
            f"estimated_cost:{estimated_cost}",
            f"quality:{model.quality_score}",
            f"latency:{model.latency_score}",
        ]
        if provider.local_provider:
            reasons.append("local_provider")
        if preferred:
            reasons.append("preferred_provider")
        return RoutingCandidate(
            provider_id=provider.id,
            provider_key=provider.provider_key,
            model_key=model.model_key,
            estimated_cost=estimated_cost,
            score=round(score, 8),
            reasons=reasons,
        )

    def _owned(self, provider_id: UUID, workspace_id: str, requester_id: str) -> ProviderRecord | None:
        provider = self.get(provider_id, workspace_id)
        if provider is None or provider.owner_id != requester_id:
            return None
        return provider

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)


ai_connector_hub_service = AIConnectorHubService()
