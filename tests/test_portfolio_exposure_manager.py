import pytest

from backend.app.modules.portfolio_exposure_manager.schemas import (
    ExposureExecutionRequest,
    ExposureState,
    OpenPosition,
    PortfolioExposureRequest,
)
from backend.app.modules.portfolio_exposure_manager.service import (
    PortfolioExposureError,
    PortfolioExposureService,
)


def payload(**overrides):
    data = dict(
        workspace_id="ws-a",
        source_record_id="risk-1",
        source_key="risk-key-1",
        account_equity=100000,
        proposed_symbol="XAUUSD",
        proposed_side="long",
        proposed_risk_percent=0.5,
        proposed_notional_value=50000,
        proposed_asset_class="metals",
        proposed_base_currency="XAU",
        proposed_quote_currency="USD",
        upstream_evidence_approved=True,
        confidence_score=88,
    )
    data.update(overrides)
    return PortfolioExposureRequest(**data)


def test_approves_clean_portfolio_after_human_review():
    svc = PortfolioExposureService()
    record = svc.assess(payload())
    assert record.state == ExposureState.HUMAN_REVIEW_REQUIRED
    assert record.approved_risk_percent == 0.5

    record = svc.execute(
        "ws-a",
        record.record_id,
        ExposureExecutionRequest(action="approve", approval_token="approval-1"),
    )
    assert record.state == ExposureState.APPROVED

    record = svc.execute(
        "ws-a",
        record.record_id,
        ExposureExecutionRequest(action="issue", downstream_receipt="receipt-1"),
    )
    assert record.state == ExposureState.ISSUED_TO_EXECUTION_BOUNDARY


def test_blocks_total_portfolio_risk():
    svc = PortfolioExposureService()
    record = svc.assess(
        payload(
            open_positions=[
                OpenPosition(
                    position_id="p1",
                    symbol="EURUSD",
                    side="long",
                    risk_percent=2.7,
                    notional_value=100000,
                )
            ]
        )
    )
    assert record.state == ExposureState.BLOCKED
    assert "maximum total portfolio risk exceeded" in record.reasons


def test_blocks_correlated_exposure():
    svc = PortfolioExposureService()
    record = svc.assess(
        payload(
            open_positions=[
                OpenPosition(
                    position_id="p1",
                    symbol="XAGUSD",
                    side="long",
                    risk_percent=1.2,
                    notional_value=40000,
                    asset_class="metals",
                )
            ],
            correlation_matrix={"XAUUSD": {"XAGUSD": 0.9}},
        )
    )
    assert record.state == ExposureState.BLOCKED
    assert "maximum correlated exposure exceeded" in record.reasons


def test_requires_upstream_evidence_and_respects_risk_brain():
    svc = PortfolioExposureService()
    missing = svc.assess(payload(upstream_evidence_approved=False))
    assert missing.state == ExposureState.EVIDENCE_REQUIRED

    blocked = svc.assess(
        payload(source_key="risk-key-2", risk_brain_hard_block=True)
    )
    assert blocked.state == ExposureState.BLOCKED


def test_replay_and_workspace_isolation():
    svc = PortfolioExposureService()
    first = svc.assess(payload())
    svc.execute(
        "ws-a",
        first.record_id,
        ExposureExecutionRequest(action="approve", approval_token="same-token"),
    )

    second = svc.assess(payload(source_key="risk-key-2", source_record_id="risk-2"))
    with pytest.raises(PortfolioExposureError, match="replay"):
        svc.execute(
            "ws-a",
            second.record_id,
            ExposureExecutionRequest(action="approve", approval_token="same-token"),
        )

    with pytest.raises(PortfolioExposureError, match="not found"):
        svc.get("ws-b", first.record_id)

    assert svc.list("ws-b") == []
    assert svc.audit("ws-b") == []


def test_duplicate_source_key_is_rejected():
    svc = PortfolioExposureService()
    svc.assess(payload())
    with pytest.raises(PortfolioExposureError, match="duplicate source key"):
        svc.assess(payload(source_record_id="risk-duplicate"))
