import pytest

from app.schemas.third_party_supply_chain_risk import ThirdPartyObservation, ThirdPartyRiskCreate, ThirdPartyRiskState
from app.services.third_party_supply_chain_risk import ThirdPartySupplyChainRiskService


def payload(**overrides):
    observation = ThirdPartyObservation(
        provider_id="vendor-1",
        provider_name="Primary Market Data Vendor",
        service_domain="market-data",
        criticality=0.80,
        due_diligence_coverage=0.95,
        security_assurance=0.92,
        privacy_assurance=0.90,
        operational_resilience=0.91,
        financial_health=0.88,
        subcontractor_transparency=0.85,
        concentration_dependency=0.30,
        contract_control_coverage=0.90,
        exit_plan_readiness=0.82,
        incident_history_score=0.10,
        open_high_findings=0,
        jurisdiction_risk=0.15,
        freshness=0.95,
        confidence=0.95,
    )
    values = {
        "workspace_id": "ws-1",
        "source_key": "snapshot-1",
        "requested_by": "risk-agent",
        "observations": [observation],
    }
    values.update(overrides)
    return ThirdPartyRiskCreate(**values)


def test_healthy_provider_assessment_is_evidence_ready():
    service = ThirdPartySupplyChainRiskService()
    record = service.create(payload())
    assert record.state == ThirdPartyRiskState.EVIDENCE_READY
    assert record.risk_flags == []
    assert record.scores.aggregate_assurance > 0.70
    assert record.dispositions[0].lifecycle_signal == "acceptable"


def test_concentration_and_exit_risk_generate_governed_actions():
    service = ThirdPartySupplyChainRiskService()
    risky = payload(observations=[ThirdPartyObservation(
        provider_id="vendor-2",
        provider_name="Critical Cloud Vendor",
        service_domain="compute",
        criticality=0.85,
        due_diligence_coverage=0.90,
        security_assurance=0.85,
        privacy_assurance=0.85,
        operational_resilience=0.80,
        financial_health=0.85,
        subcontractor_transparency=0.70,
        concentration_dependency=0.90,
        contract_control_coverage=0.82,
        exit_plan_readiness=0.40,
        incident_history_score=0.15,
        open_high_findings=0,
        jurisdiction_risk=0.20,
    )])
    record = service.create(risky)
    actions = record.dispositions[0].required_actions
    assert "concentration-and-substitutability-review" in actions
    assert "exit-and-transition-plan-review" in actions
    assert any(flag.startswith("concentration-alert:") for flag in record.risk_flags)


def test_critical_high_risk_provider_triggers_risk_brain_hard_block():
    service = ThirdPartySupplyChainRiskService()
    critical = payload(observations=[ThirdPartyObservation(
        provider_id="vendor-critical",
        provider_name="Critical Execution Dependency",
        service_domain="execution-connectivity",
        criticality=0.98,
        due_diligence_coverage=0.20,
        security_assurance=0.25,
        privacy_assurance=0.30,
        operational_resilience=0.20,
        financial_health=0.40,
        subcontractor_transparency=0.15,
        concentration_dependency=0.95,
        contract_control_coverage=0.25,
        exit_plan_readiness=0.10,
        incident_history_score=0.90,
        open_high_findings=5,
        jurisdiction_risk=0.80,
    )])
    record = service.create(critical)
    assert record.state == ThirdPartyRiskState.BLOCKED
    assert "risk-brain-hard-block" in record.risk_flags


def test_unresolved_findings_block_approval():
    service = ThirdPartySupplyChainRiskService()
    risky = payload(observations=[payload().observations[0].model_copy(update={"contract_control_coverage": 0.40})])
    record = service.create(risky)
    with pytest.raises(ValueError, match="unresolved third-party risk flags block approval"):
        service.act("ws-1", record.record_id, "approve", "human", "op-1")


def test_activation_requires_human_approval():
    service = ThirdPartySupplyChainRiskService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required before activation"):
        service.act("ws-1", record.record_id, "activate", "human", "op-1")


def test_operation_replay_is_rejected():
    service = ThirdPartySupplyChainRiskService()
    record = service.create(payload())
    service.act("ws-1", record.record_id, "assess", "analyst", "same-op")
    with pytest.raises(ValueError, match="operation replay detected"):
        service.act("ws-1", record.record_id, "submit-review", "analyst", "same-op")


def test_workspace_isolation_and_duplicate_source_key():
    service = ThirdPartySupplyChainRiskService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("other-ws", record.record_id)
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())


def test_status_exposes_safety_boundary():
    status = ThirdPartySupplyChainRiskService().status()
    assert status["governance_only"] is True
    assert status["vendor_mutation_enabled"] is False
    assert status["contract_mutation_enabled"] is False
    assert status["access_mutation_enabled"] is False
    assert status["execution_enabled"] is False
    assert status["risk_brain_authoritative"] is True
