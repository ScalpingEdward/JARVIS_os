import pytest
from pydantic import ValidationError

from app.ai_connector_hub.models import (
    ModelProfile,
    ProviderMutation,
    ProviderRegister,
    ProviderState,
    ProviderType,
    RoutingRequest,
    RoutingStrategy,
    UsageRecordCreate,
)
from app.ai_connector_hub.service import AIConnectorHubService


def provider_payload(
    key: str = "openai-main",
    owner: str = "owner-1",
    workspace: str = "workspace-1",
    local: bool = False,
    input_cost: float = 2.0,
) -> ProviderRegister:
    return ProviderRegister(
        workspace_id=workspace,
        owner_id=owner,
        provider_key=key,
        provider_type=ProviderType.OLLAMA if local else ProviderType.OPENAI,
        display_name=key,
        local_provider=local,
        monthly_budget=20.0,
        models=[
            ModelProfile(
                model_key=f"{key}-model",
                capabilities=["text.generate", "code.generate"],
                input_cost_per_million=input_cost,
                output_cost_per_million=input_cost * 2,
                quality_score=0.8,
                latency_score=0.7,
            )
        ],
    )


def activate(service: AIConnectorHubService, provider):
    return service.activate(
        provider.id,
        provider.workspace_id,
        provider.owner_id,
        ProviderMutation(reason="approved activation"),
    )


def test_register_activate_and_route_dry_run():
    service = AIConnectorHubService()
    provider = service.register(provider_payload())
    assert provider.state == ProviderState.REGISTERED
    activate(service, provider)

    decision = service.route(
        RoutingRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            capability="text.generate",
            estimated_input_tokens=1000,
            estimated_output_tokens=500,
        )
    )
    assert decision.selected is not None
    assert decision.provider_request_executed is False
    assert decision.dry_run is True


def test_workspace_isolation_blocks_cross_workspace_provider():
    service = AIConnectorHubService()
    provider = service.register(provider_payload())
    activate(service, provider)
    decision = service.route(
        RoutingRequest(
            workspace_id="other-workspace",
            requester_id="owner-1",
            capability="text.generate",
        )
    )
    assert decision.selected is None
    assert decision.blocked_reason


def test_lowest_cost_selects_cheaper_model():
    service = AIConnectorHubService()
    expensive = service.register(provider_payload(key="expensive", input_cost=10.0))
    cheap = service.register(provider_payload(key="cheap", input_cost=0.1))
    activate(service, expensive)
    activate(service, cheap)

    decision = service.route(
        RoutingRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            capability="text.generate",
            strategy=RoutingStrategy.LOWEST_COST,
            estimated_input_tokens=100000,
            estimated_output_tokens=100000,
            maximum_estimated_cost=10,
        )
    )
    assert decision.selected is not None
    assert decision.selected.provider_key == "cheap"


def test_local_first_prefers_local_provider():
    service = AIConnectorHubService()
    cloud = service.register(provider_payload(key="cloud"))
    local = service.register(provider_payload(key="ollama-local", local=True, input_cost=0.0))
    activate(service, cloud)
    activate(service, local)

    decision = service.route(
        RoutingRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            capability="code.generate",
            strategy=RoutingStrategy.LOCAL_FIRST,
        )
    )
    assert decision.selected is not None
    assert decision.selected.provider_key == "ollama-local"


def test_budget_limit_blocks_candidate():
    service = AIConnectorHubService()
    payload = provider_payload(input_cost=100.0)
    payload.monthly_budget = 0.01
    provider = service.register(payload)
    activate(service, provider)
    decision = service.route(
        RoutingRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            capability="text.generate",
            estimated_input_tokens=1000000,
            maximum_estimated_cost=500,
        )
    )
    assert decision.selected is None


def test_usage_updates_spend_and_degrades_at_budget():
    service = AIConnectorHubService()
    payload = provider_payload()
    payload.monthly_budget = 1.0
    provider = service.register(payload)
    activate(service, provider)
    record = service.record_usage(
        UsageRecordCreate(
            workspace_id="workspace-1",
            provider_id=provider.id,
            model_key="openai-main-model",
            actual_cost=1.0,
        )
    )
    assert record is not None
    assert provider.current_month_spend == 1.0
    assert provider.state == ProviderState.DEGRADED


def test_owner_only_activation():
    service = AIConnectorHubService()
    provider = service.register(provider_payload())
    result = service.activate(
        provider.id,
        "workspace-1",
        "wrong-owner",
        ProviderMutation(reason="not allowed"),
    )
    assert result is None


def test_duplicate_provider_key_rejected():
    service = AIConnectorHubService()
    service.register(provider_payload())
    with pytest.raises(ValueError):
        service.register(provider_payload())


def test_real_execution_and_automatic_paid_requests_rejected():
    with pytest.raises(ValidationError):
        RoutingRequest(
            workspace_id="workspace-1",
            requester_id="owner-1",
            capability="text.generate",
            execute_provider_request=True,
        )
    with pytest.raises(ValidationError):
        ProviderRegister(
            workspace_id="workspace-1",
            owner_id="owner-1",
            provider_key="paid-provider",
            provider_type=ProviderType.OPENAI,
            display_name="Paid provider",
            models=[ModelProfile(model_key="paid-model", capabilities=["text.generate"])],
            automatic_paid_requests=True,
        )


def test_status_reports_safety_defaults():
    service = AIConnectorHubService()
    status = service.status()
    assert status.version == "8.1"
    assert status.dry_run_only is True
    assert status.real_provider_execution is False
    assert status.automatic_paid_requests is False
