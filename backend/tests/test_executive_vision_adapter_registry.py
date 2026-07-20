import pytest

from app.executive_vision_adapter_registry.models import (
    AdapterHealthObservation,
    AdapterRegistryAssessmentCreate,
    AdapterRegistryState,
)
from app.executive_vision_adapter_registry.service import ExecutiveVisionAdapterRegistryService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="tester",
        provider_id="openai",
        adapter_id="openai-vision",
        version="1.0.0",
        health=AdapterHealthObservation(
            available=True,
            success_rate_pct=99,
            p95_latency_ms=3000,
            consecutive_failures=0,
            quota_remaining_pct=80,
            daily_cost_units=10,
            estimated_request_cost_units=1,
            credential_reference_configured=True,
        ),
    )
    data.update(overrides)
    return AdapterRegistryAssessmentCreate(**data)


def test_eligible_adapter_is_routable():
    result = ExecutiveVisionAdapterRegistryService().create(payload())
    assert result.state == AdapterRegistryState.eligible
    assert result.routable is True
    assert result.executable is True


def test_human_preferred_adapter_is_preferred():
    result = ExecutiveVisionAdapterRegistryService().create(payload(human_preferred=True))
    assert result.state == AdapterRegistryState.preferred


def test_missing_credentials_is_unavailable():
    request = payload(health=AdapterHealthObservation(credential_reference_configured=False))
    result = ExecutiveVisionAdapterRegistryService().create(request)
    assert result.state == AdapterRegistryState.unavailable
    assert result.routable is False


def test_quota_or_health_breach_constrains_adapter():
    request = payload(health=AdapterHealthObservation(
        available=True,
        success_rate_pct=90,
        p95_latency_ms=3000,
        quota_remaining_pct=5,
        credential_reference_configured=True,
    ))
    result = ExecutiveVisionAdapterRegistryService().create(request)
    assert result.state == AdapterRegistryState.constrained


def test_risk_brain_blocks_adapter():
    result = ExecutiveVisionAdapterRegistryService().create(payload(risk_brain_clear=False))
    assert result.state == AdapterRegistryState.blocked


def test_duplicate_and_workspace_isolation():
    service = ExecutiveVisionAdapterRegistryService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
