from datetime import UTC, datetime

import pytest

from app.schemas.market_microstructure_liquidity import (
    MicrostructureAction,
    MicrostructureRecordCreate,
    MicrostructureState,
    VenueObservation,
)
from app.services.market_microstructure_liquidity import MarketMicrostructureStore


def payload(workspace: str = "alpha", source_key: str = "feed-1") -> MicrostructureRecordCreate:
    now = datetime.now(UTC)
    return MicrostructureRecordCreate(
        workspace_id=workspace,
        source_key=source_key,
        asset_class="equities",
        provenance_confidence=0.94,
        freshness_score=0.91,
        observations=[
            VenueObservation(
                venue="XNAS",
                instrument="AAPL",
                bid=210.10,
                ask=210.12,
                bid_size=1200,
                ask_size=800,
                traded_volume=25000,
                cancel_rate=0.18,
                latency_ms=2.5,
                observed_at=now,
            ),
            VenueObservation(
                venue="BATS",
                instrument="AAPL",
                bid=210.09,
                ask=210.13,
                bid_size=700,
                ask_size=1100,
                traded_volume=18000,
                cancel_rate=0.22,
                latency_ms=3.1,
                observed_at=now,
            ),
        ],
    )


def action(name: str, receipt: str, blocked: bool = False) -> MicrostructureAction:
    return MicrostructureAction(
        action=name,
        actor="risk-officer",
        operation_receipt=receipt,
        risk_brain_blocked=blocked,
    )


def test_scoring_and_approval_lifecycle() -> None:
    store = MarketMicrostructureStore()
    record = store.create(payload())
    scored = store.act(record.id, "alpha", action("score", "receipt-001"))
    assert scored.state == MicrostructureState.SCORED
    assert scored.scores is not None
    assert -100 <= scored.scores.order_flow_imbalance <= 100

    review = store.act(record.id, "alpha", action("submit-review", "receipt-002"))
    assert review.state == MicrostructureState.REVIEW_REQUIRED
    approved = store.act(record.id, "alpha", action("approve", "receipt-003"))
    assert approved.state == MicrostructureState.APPROVED
    active = store.act(record.id, "alpha", action("activate", "receipt-004"))
    assert active.state == MicrostructureState.ACTIVE


def test_risk_brain_hard_block_is_authoritative() -> None:
    store = MarketMicrostructureStore()
    record = store.create(payload())
    blocked = store.act(record.id, "alpha", action("activate", "receipt-005", blocked=True))
    assert blocked.state == MicrostructureState.BLOCKED


def test_receipt_replay_and_workspace_isolation() -> None:
    store = MarketMicrostructureStore()
    record = store.create(payload())
    store.act(record.id, "alpha", action("score", "receipt-006"))
    with pytest.raises(ValueError, match="already used"):
        store.act(record.id, "alpha", action("score", "receipt-006"))
    with pytest.raises(KeyError):
        store.get(record.id, "other-workspace")


def test_duplicate_source_key_rejected_per_workspace() -> None:
    store = MarketMicrostructureStore()
    store.create(payload())
    with pytest.raises(ValueError, match="duplicate"):
        store.create(payload())
    store.create(payload(workspace="beta"))
