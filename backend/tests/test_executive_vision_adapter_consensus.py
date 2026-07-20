import pytest

from app.executive_vision_adapter_consensus.models import (
    AdapterExtraction,
    ConsensusAssessmentCreate,
    ConsensusPolicy,
    ConsensusState,
)
from app.executive_vision_adapter_consensus.service import ExecutiveVisionAdapterConsensusService


def extraction(provider_id: str, **overrides):
    data = dict(
        provider_id=provider_id,
        invocation_id=f"inv-{provider_id}",
        success=True,
        schema_valid=True,
        safety_clear=True,
        confidence=90,
        symbol="XAUUSD",
        timeframe="M15",
        direction="long",
        entry_price=2400.0,
        stop_loss=2390.0,
        take_profits=[2420.0, 2440.0],
        ict_features=["liquidity-sweep", "fair-value-gap"],
    )
    data.update(overrides)
    return AdapterExtraction(**data)


def payload(**overrides):
    data = dict(
        workspace_id="ws-1",
        source_key="source-1",
        actor_id="tester",
        routing_assessment_id="routing-1",
        routing_state="dispatched",
        image_sha256="a" * 64,
        risk_brain_clear=True,
        human_approved=False,
        extractions=[extraction("primary"), extraction("fallback", entry_price=2400.2)],
    )
    data.update(overrides)
    return ConsensusAssessmentCreate(**data)


def test_consensus_dispatches_normalized_extraction():
    result = ExecutiveVisionAdapterConsensusService().create(payload())
    assert result.state == ConsensusState.dispatched
    assert result.dispatchable is True
    assert result.normalized_extraction.direction == "long"
    assert len(result.normalized_extraction.agreeing_provider_ids) == 2


def test_direction_disagreement_is_blocked():
    request = payload(extractions=[extraction("a"), extraction("b", direction="short")])
    result = ExecutiveVisionAdapterConsensusService().create(request)
    assert result.state == ConsensusState.disagreement
    assert result.dispatchable is False


def test_large_entry_deviation_requires_review():
    request = payload(extractions=[extraction("a", entry_price=2400), extraction("b", entry_price=2420)])
    result = ExecutiveVisionAdapterConsensusService().create(request)
    assert result.state == ConsensusState.disagreement


def test_single_adapter_requires_human_override():
    request = payload(
        extractions=[extraction("primary")],
        policy=ConsensusPolicy(minimum_agreeing_adapters=2),
    )
    result = ExecutiveVisionAdapterConsensusService().create(request)
    assert result.state == ConsensusState.disagreement

    approved = payload(
        source_key="source-2",
        image_sha256="b" * 64,
        extractions=[extraction("primary")],
        policy=ConsensusPolicy(minimum_agreeing_adapters=2),
        human_approved=True,
    )
    assert ExecutiveVisionAdapterConsensusService().create(approved).state == ConsensusState.dispatched


def test_risk_brain_blocks_consensus():
    result = ExecutiveVisionAdapterConsensusService().create(payload(risk_brain_clear=False))
    assert result.state == ConsensusState.blocked


def test_duplicate_and_workspace_isolation():
    service = ExecutiveVisionAdapterConsensusService()
    first = service.create(payload())
    with pytest.raises(ValueError):
        service.create(payload())
    assert service.get(first.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
