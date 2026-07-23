import pytest

from app.phoenix.options_flow_gamma.models import OptionObservation, OptionsFlowState
from app.phoenix.options_flow_gamma.service import (
    OptionsFlowGovernanceError,
    OptionsFlowGovernanceService,
)


def observation(source_key: str = "feed-1", strike: float = 5000.0) -> OptionObservation:
    return OptionObservation(
        source_key=source_key,
        underlying="SPX",
        expiry="2026-12-18",
        strike=strike,
        option_type="call",
        side="buy",
        premium=12.5,
        contracts=100,
        gamma=0.02,
        vega=0.4,
        implied_volatility=0.22,
        open_interest=1_000,
        volume=500,
        confidence=0.9,
        freshness=0.95,
        provenance="exchange",
    )


def test_record_scoring_and_human_approval_lifecycle() -> None:
    service = OptionsFlowGovernanceService()
    record = service.create_record("alpha", [observation()])

    assert record.state == OptionsFlowState.SCORED
    assert record.net_premium == 1250.0
    assert record.quality_score > 0.9

    service.apply_action("alpha", record.record_id, "submit", "op-1")
    service.apply_action("alpha", record.record_id, "approve", "op-2")
    active = service.apply_action("alpha", record.record_id, "activate", "op-3")

    assert active.human_approved is True
    assert active.state in {
        OptionsFlowState.ACTIVE,
        OptionsFlowState.GAMMA_SHIFT,
        OptionsFlowState.VOLATILITY_SHIFT,
        OptionsFlowState.ESCALATED,
    }


def test_activation_requires_human_approval() -> None:
    service = OptionsFlowGovernanceService()
    record = service.create_record("alpha", [observation()])

    with pytest.raises(OptionsFlowGovernanceError, match="human approval"):
        service.apply_action("alpha", record.record_id, "activate", "op-1")


def test_risk_brain_block_is_authoritative() -> None:
    service = OptionsFlowGovernanceService()
    record = service.create_record("alpha", [observation()])

    blocked = service.apply_action(
        "alpha", record.record_id, "submit", "op-1", risk_brain_blocked=True
    )

    assert blocked.state == OptionsFlowState.BLOCKED


def test_replay_and_workspace_isolation() -> None:
    service = OptionsFlowGovernanceService()
    record = service.create_record("alpha", [observation()])
    service.apply_action("alpha", record.record_id, "submit", "same-operation")

    with pytest.raises(OptionsFlowGovernanceError, match="replay"):
        service.apply_action("alpha", record.record_id, "submit", "same-operation")

    with pytest.raises(OptionsFlowGovernanceError, match="not found"):
        service.get_record("beta", record.record_id)


def test_duplicate_source_keys_are_rejected() -> None:
    service = OptionsFlowGovernanceService()

    with pytest.raises(OptionsFlowGovernanceError, match="duplicate source_key"):
        service.create_record("alpha", [observation("dup"), observation("dup", 5100.0)])
