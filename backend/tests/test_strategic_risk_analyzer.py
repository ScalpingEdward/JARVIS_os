import pytest

from app.modules.strategic_risk_analyzer.models import (
    RiskSignal,
    RiskState,
    StrategicRiskCreate,
    StrategicRiskExecute,
)
from app.modules.strategic_risk_analyzer.service import StrategicRiskService


def payload(workspace: str = "alpha", source: str = "kpi-1") -> StrategicRiskCreate:
    return StrategicRiskCreate(
        workspace_id=workspace,
        source_key=source,
        executive_kpi_record_id="kpi-record-1",
        executive_kpi_approved=True,
        executive_kpi_evidence=["approval:abc", "audit:def"],
        risk_brain_status="clear",
        portfolio_confidence=82,
        risk_appetite=45,
        max_residual_exposure=40,
        signals=[
            RiskSignal(
                title="Cloud dependency concentration",
                category="dependency",
                probability=0.55,
                impact=70,
                velocity=65,
                detectability=70,
                owner="CTO",
                mitigation="Maintain tested secondary provider and portable deployment artifacts",
                contingency="Activate failover provider and freeze non-essential releases",
            ),
            RiskSignal(
                title="Budget variance",
                category="financial",
                probability=0.3,
                impact=45,
                velocity=35,
                detectability=85,
                owner="CFO",
                mitigation="Review spend weekly and enforce category ceilings",
                contingency="Reduce discretionary cloud and model usage",
            ),
        ],
    )


def test_analysis_approval_and_issue() -> None:
    service = StrategicRiskService()
    record = service.create(payload())
    assert record.state == RiskState.ANALYSIS_PENDING

    analyzed = service.execute(
        record.record_id,
        "alpha",
        StrategicRiskExecute(action="analyze", actor="risk-officer"),
    )
    assert analyzed.assessments
    assert analyzed.aggregate_residual_risk >= 0
    assert analyzed.state in {RiskState.RISK_REGISTER_READY, RiskState.HUMAN_REVIEW_REQUIRED}

    approved = service.execute(
        record.record_id,
        "alpha",
        StrategicRiskExecute(action="approve", actor="ceo", reason="risk treatment accepted"),
    )
    assert approved.state == RiskState.APPROVED
    assert approved.approval_token

    issued = service.execute(
        record.record_id,
        "alpha",
        StrategicRiskExecute(
            action="issue",
            actor="ceo",
            approval_token=approved.approval_token,
            receipt="investment-receipt-1",
        ),
    )
    assert issued.state == RiskState.ISSUED_TO_INVESTMENT_DECISION


def test_risk_brain_blocks_record() -> None:
    service = StrategicRiskService()
    blocked_payload = payload(source="blocked")
    blocked_payload.risk_brain_status = "blocked"
    record = service.create(blocked_payload)
    assert record.state == RiskState.BLOCKED


def test_dependency_block_fails_closed() -> None:
    service = StrategicRiskService()
    blocked_payload = payload(source="dependency-blocked")
    blocked_payload.signals[0].dependency_blocked = True
    record = service.create(blocked_payload)
    assert record.state == RiskState.BLOCKED


def test_duplicate_source_and_receipt_replay_rejected() -> None:
    service = StrategicRiskService()
    first = service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())

    analyzed = service.execute(first.record_id, "alpha", StrategicRiskExecute(action="analyze", actor="analyst"))
    approved = service.execute(
        first.record_id,
        "alpha",
        StrategicRiskExecute(action="approve", actor="ceo", reason="accepted"),
    )
    service.execute(
        first.record_id,
        "alpha",
        StrategicRiskExecute(
            action="issue",
            actor="ceo",
            approval_token=approved.approval_token,
            receipt="same-receipt",
        ),
    )

    second = service.create(payload(source="kpi-2"))
    service.execute(second.record_id, "alpha", StrategicRiskExecute(action="analyze", actor="analyst"))
    second_approved = service.execute(
        second.record_id,
        "alpha",
        StrategicRiskExecute(action="approve", actor="ceo", reason="accepted"),
    )
    with pytest.raises(ValueError, match="receipt replay"):
        service.execute(
            second.record_id,
            "alpha",
            StrategicRiskExecute(
                action="issue",
                actor="ceo",
                approval_token=second_approved.approval_token,
                receipt="same-receipt",
            ),
        )


def test_workspace_isolation() -> None:
    service = StrategicRiskService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get(record.record_id, "other")
    assert service.list("other") == []
