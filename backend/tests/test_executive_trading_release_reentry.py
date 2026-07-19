import pytest

from app.executive_trading_release_reentry.models import (
    ReleaseAssessmentCreate,
    ReleaseGate,
    ReleaseState,
    VerificationState,
)
from app.executive_trading_release_reentry.service import ExecutiveTradingReleaseReentryService


def payload(**overrides):
    data = {
        "workspace_id": "ws-1",
        "actor_id": "risk-officer",
        "source_key": "release-1",
        "symbol": "XAUUSD",
        "account_profile": "ftmo-100k",
        "incident_recovery_state": "verified",
        "readiness_state": "ready",
        "risk_state": "normal",
        "trading_decision": "approve",
        "data_integrity_score": 95,
        "recovery_confidence": 92,
        "stability_score": 90,
        "human_release_approved": True,
        "verification_gates": [
            ReleaseGate(name="broker-health", state=VerificationState.passed, score=95),
            ReleaseGate(name="feed-health", state=VerificationState.passed, score=94),
        ],
    }
    data.update(overrides)
    return ReleaseAssessmentCreate(**data)


def test_full_release_when_all_gates_pass():
    service = ExecutiveTradingReleaseReentryService()
    result = service.assess(payload())
    assert result.state == ReleaseState.full_live
    assert result.approved_risk_multiplier == 1
    assert len(result.reentry_plan) == 4


def test_human_approval_is_mandatory():
    service = ExecutiveTradingReleaseReentryService()
    result = service.assess(payload(human_release_approved=False))
    assert result.state == ReleaseState.shadow_only
    assert result.approved_risk_multiplier == 0


def test_critical_incident_blocks_release():
    service = ExecutiveTradingReleaseReentryService()
    result = service.assess(payload(open_critical_incidents=1))
    assert result.state == ReleaseState.blocked
    assert result.approved_risk_multiplier == 0


def test_warning_routes_to_reduced_live():
    service = ExecutiveTradingReleaseReentryService()
    result = service.assess(payload(
        verification_gates=[ReleaseGate(name="latency", state=VerificationState.warning, score=70, blocking=False)]
    ))
    assert result.state == ReleaseState.reduced_live
    assert result.approved_risk_multiplier <= 0.5


def test_failed_blocking_gate_prevents_release():
    service = ExecutiveTradingReleaseReentryService()
    result = service.assess(payload(
        verification_gates=[ReleaseGate(name="data-checksum", state=VerificationState.failed, score=20, blocking=True)]
    ))
    assert result.state == ReleaseState.blocked
    assert "data-checksum" in result.failed_gates


def test_workspace_isolation_and_duplicate_protection():
    service = ExecutiveTradingReleaseReentryService()
    created = service.assess(payload())
    assert service.get(created.id, "other") is None
    assert len(service.list_assessments("ws-1")) == 1
    with pytest.raises(ValueError):
        service.assess(payload())
