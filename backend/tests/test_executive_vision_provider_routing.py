import pytest

from app.executive_vision_provider_routing.models import ProviderObservation, VisionRoutingAssessmentCreate, VisionRoutingPolicy, VisionRoutingState
from app.executive_vision_provider_routing.service import ExecutiveVisionProviderRoutingService


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="src-1",
        actor_id="tester",
        ingestion_id="ing-1",
        image_sha256="a" * 64,
        providers=[ProviderObservation(provider_id="primary", available=True, latency_ms=900, estimated_cost_units=2, extraction_confidence=92, schema_valid=True)],
    )
    data.update(overrides)
    return VisionRoutingAssessmentCreate(**data)


def test_primary_dispatch():
    result = ExecutiveVisionProviderRoutingService().create(payload())
    assert result.state == VisionRoutingState.dispatched
    assert result.selected_provider_id == "primary"
    assert result.dispatchable is True


def test_fallback_dispatch():
    providers = [
        ProviderObservation(provider_id="primary", available=False),
        ProviderObservation(provider_id="backup", available=True, latency_ms=1200, estimated_cost_units=3, extraction_confidence=90, schema_valid=True),
    ]
    result = ExecutiveVisionProviderRoutingService().create(payload(providers=providers))
    assert result.state == VisionRoutingState.dispatched
    assert result.fallback_used is True
    assert result.selected_provider_id == "backup"


def test_fallback_approval_gate():
    providers = [ProviderObservation(provider_id="backup", available=True, latency_ms=1200, estimated_cost_units=3, extraction_confidence=90, schema_valid=True)]
    policy = VisionRoutingPolicy(require_human_approval_for_fallback=True)
    result = ExecutiveVisionProviderRoutingService().create(payload(providers=providers, policy=policy))
    assert result.state == VisionRoutingState.fallback_required
    assert result.dispatchable is False


def test_provider_outage_queues():
    result = ExecutiveVisionProviderRoutingService().create(payload(providers=[ProviderObservation(provider_id="primary", available=False)]))
    assert result.state == VisionRoutingState.queued


def test_risk_brain_blocks():
    result = ExecutiveVisionProviderRoutingService().create(payload(risk_brain_clear=False))
    assert result.state == VisionRoutingState.blocked


def test_duplicate_and_isolation():
    service = ExecutiveVisionProviderRoutingService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
