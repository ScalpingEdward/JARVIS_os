import pytest
from pydantic import ValidationError

from backend.app.phoenix.v21_62_global_macro_economic_regime.models import (
    CentralBankSignal, MacroAction, MacroCreate, MacroIndicator, MacroPolicy, MacroState,
)
from backend.app.phoenix.v21_62_global_macro_economic_regime.service import (
    GovernanceError, MacroGovernanceService,
)


def indicator(name, category, score, freshness=30):
    return MacroIndicator(
        name=name,
        category=category,
        region="US",
        value=score,
        previous_value=score - 1,
        normalized_score=score,
        surprise_score=5,
        freshness_minutes=freshness,
        source_ref=f"macro:{name}",
    )


def payload(**overrides):
    data = {
        "workspace_id": "workspace-a",
        "source_key": "macro-cycle-1",
        "indicators": [
            indicator("gdp-nowcast", "growth", 45),
            indicator("core-cpi", "inflation", 10),
            indicator("financial-conditions", "liquidity", 35),
            indicator("dollar-index", "currency", 15),
            indicator("ten-year-yield", "rates", 5),
        ],
        "central_banks": [CentralBankSignal(bank="FED", policy_rate=4.5, expected_rate=4.25, stance="neutral")],
        "evidence_refs": ["macro-feed:snapshot-1"],
        "policy": MacroPolicy(stable_cycles_required=2),
    }
    data.update(overrides)
    return MacroCreate(**data)


def advance(service, record_id):
    actions = [
        ("prepare-evidence", {}), ("classify", {}), ("prepare-policy", {}),
        ("request-review", {}), ("approve", {"approval_token": "approval-1"}),
        ("activate", {"operation_receipt": "activation-1"}),
    ]
    for action, extra in actions:
        service.act(record_id, "workspace-a", MacroAction(action=action, actor="operator", **extra))


def test_full_macro_governance_lifecycle():
    service = MacroGovernanceService()
    record = service.create(payload())
    assert record.regime == "expansion"
    assert record.risk_environment == "risk-on"
    advance(service, record.record_id)
    for _ in range(2):
        service.act(record.record_id, "workspace-a", MacroAction(action="observe", actor="monitor", indicators=record.indicators))
    service.act(record.record_id, "workspace-a", MacroAction(action="confirm-stable", actor="operator"))
    assert record.state == MacroState.STABLE
    assert service.audit


def test_regime_shift_and_escalation():
    service = MacroGovernanceService()
    record = service.create(payload())
    advance(service, record.record_id)
    stressed = [
        indicator("gdp-nowcast", "growth", -95),
        indicator("core-cpi", "inflation", 90),
        indicator("financial-conditions", "liquidity", -95),
        indicator("dollar-index", "currency", 90),
        indicator("ten-year-yield", "rates", 90),
    ]
    service.act(record.record_id, "workspace-a", MacroAction(action="observe", actor="monitor", indicators=stressed))
    assert record.state == MacroState.ESCALATED
    assert record.regime == "stagflation"
    assert "macro_risk_threshold_exceeded" in record.violations


def test_replay_risk_brain_duplicates_and_isolation():
    service = MacroGovernanceService()
    first = service.create(payload())
    advance(service, first.record_id)
    second = service.create(payload(source_key="macro-cycle-2"))
    for action in ["prepare-evidence", "classify", "prepare-policy", "request-review"]:
        service.act(second.record_id, "workspace-a", MacroAction(action=action, actor="operator"))
    with pytest.raises(GovernanceError, match="replay"):
        service.act(second.record_id, "workspace-a", MacroAction(action="approve", actor="operator", approval_token="approval-1"))
    blocked = service.create(payload(source_key="macro-cycle-3", risk_brain_blocked=True))
    with pytest.raises(GovernanceError, match="Risk Brain"):
        service.act(blocked.record_id, "workspace-a", MacroAction(action="prepare-evidence", actor="operator"))
    with pytest.raises(GovernanceError, match="duplicate"):
        service.create(payload())
    with pytest.raises(KeyError):
        service.get(first.record_id, "workspace-b")


def test_validation_rejects_duplicate_indicators():
    duplicate = indicator("gdp-nowcast", "growth", 20)
    with pytest.raises(ValidationError):
        MacroCreate(workspace_id="w", source_key="s", indicators=[duplicate, duplicate])
