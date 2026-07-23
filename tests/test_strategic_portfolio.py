import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_53_strategic_portfolio.models import (
    CorrelationPair,
    ExposureConstraint,
    PortfolioActionRequest,
    PortfolioSleeve,
    PortfolioState,
    RiskDecision,
    StrategicPortfolioCreate,
)
from backend.app.phoenix.v21_53_strategic_portfolio.service import (
    StrategicPortfolioError,
    StrategicPortfolioService,
)


def payload(**overrides):
    data = {
        "workspace_id": "ws-1",
        "source_key": "portfolio-1",
        "executive_record_id": "exec-1",
        "portfolio_name": "Institutional Alpha Portfolio",
        "total_capital": 1_000_000,
        "sleeves": [
            PortfolioSleeve(
                sleeve_id="s1",
                strategy_id="trend",
                name="Trend",
                target_weight=0.4,
                maximum_weight=0.5,
                expected_return=0.18,
                expected_volatility=0.12,
                liquidity_score=0.9,
                confidence=0.92,
                evidence_refs=["ev-trend"],
            ),
            PortfolioSleeve(
                sleeve_id="s2",
                strategy_id="mean-reversion",
                name="Mean Reversion",
                target_weight=0.35,
                maximum_weight=0.5,
                expected_return=0.14,
                expected_volatility=0.09,
                liquidity_score=0.85,
                confidence=0.9,
                evidence_refs=["ev-mean"],
            ),
            PortfolioSleeve(
                sleeve_id="s3",
                strategy_id="defensive",
                name="Defensive",
                target_weight=0.25,
                maximum_weight=0.5,
                expected_return=0.08,
                expected_volatility=0.05,
                liquidity_score=0.95,
                confidence=0.88,
                evidence_refs=["ev-def"],
            ),
        ],
        "exposure_constraints": [
            ExposureConstraint(
                constraint_id="c1",
                dimension="USD",
                current_exposure=0.35,
                maximum_absolute_exposure=0.6,
                evidence_refs=["ev-usd"],
            )
        ],
        "correlations": [
            CorrelationPair(left_sleeve_id="s1", right_sleeve_id="s2", correlation=0.35)
        ],
        "maximum_single_sleeve_weight": 0.5,
        "required_healthy_cycles": 2,
        "portfolio_evidence_refs": ["ev-portfolio"],
    }
    data.update(overrides)
    return StrategicPortfolioCreate(**data)


def action(name, **kwargs):
    return PortfolioActionRequest(action=name, actor="tester", **kwargs)


def test_full_lifecycle_and_audit():
    service = StrategicPortfolioService()
    record = service.create(payload())
    assert record.state == PortfolioState.DRAFT

    service.act(record.record_id, "ws-1", action("prepare-evidence"))
    service.act(record.record_id, "ws-1", action("analyze"))
    service.act(record.record_id, "ws-1", action("prepare-allocation"))
    service.act(record.record_id, "ws-1", action("request-review"))
    service.act(record.record_id, "ws-1", action("approve", approval_token="approve-1"))
    service.act(
        record.record_id,
        "ws-1",
        action("orchestrate", receipt_id="receipt-1", evidence_refs=["execution-1"]),
    )
    service.act(record.record_id, "ws-1", action("record-cycle", cycle_healthy=True))
    service.act(record.record_id, "ws-1", action("record-cycle", cycle_healthy=True))
    result = service.act(record.record_id, "ws-1", action("verify"))

    assert result.state == PortfolioState.VERIFIED
    assert len(service.audit("ws-1")) == 10


def test_concentration_breach_escalates_analysis():
    service = StrategicPortfolioService()
    record = service.create(payload(maximum_single_sleeve_weight=0.3))
    service.act(record.record_id, "ws-1", action("prepare-evidence"))
    result = service.act(record.record_id, "ws-1", action("analyze"))
    assert result.state == PortfolioState.ESCALATED
    assert result.concentration_breaches == 2


def test_risk_brain_block_is_authoritative():
    service = StrategicPortfolioService()
    record = service.create(payload(risk_decision=RiskDecision.BLOCK, risk_reason="risk ceiling"))
    result = service.act(record.record_id, "ws-1", action("prepare-evidence"))
    assert result.state == PortfolioState.BLOCKED


def test_replay_protection():
    service = StrategicPortfolioService()
    first = service.create(payload())
    for name in ["prepare-evidence", "analyze", "prepare-allocation", "request-review"]:
        service.act(first.record_id, "ws-1", action(name))
    service.act(first.record_id, "ws-1", action("approve", approval_token="same-token"))

    second = service.create(payload(source_key="portfolio-2"))
    for name in ["prepare-evidence", "analyze", "prepare-allocation", "request-review"]:
        service.act(second.record_id, "ws-1", action(name))
    with pytest.raises(StrategicPortfolioError, match="replay"):
        service.act(second.record_id, "ws-1", action("approve", approval_token="same-token"))


def test_workspace_isolation_and_duplicate_source():
    service = StrategicPortfolioService()
    record = service.create(payload())
    with pytest.raises(StrategicPortfolioError, match="not found"):
        service.get(record.record_id, "ws-2")
    with pytest.raises(StrategicPortfolioError, match="duplicate source key"):
        service.create(payload())


def test_target_weights_must_sum_to_one():
    sleeves = payload().sleeves
    sleeves[0].target_weight = 0.2
    with pytest.raises(ValidationError, match="sum to 1"):
        payload(sleeves=sleeves)


def test_low_confidence_blocks_allocation_preparation():
    service = StrategicPortfolioService()
    sleeves = payload().sleeves
    sleeves[0].confidence = 0.2
    record = service.create(payload(source_key="low-confidence", sleeves=sleeves))
    service.act(record.record_id, "ws-1", action("prepare-evidence"))
    service.act(record.record_id, "ws-1", action("analyze"))
    with pytest.raises(StrategicPortfolioError, match="confidence"):
        service.act(record.record_id, "ws-1", action("prepare-allocation"))
