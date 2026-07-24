import pytest

from app.schemas.configuration_asset_integrity import ConfigurationAssetCreate
from app.services.configuration_asset_integrity import ConfigurationAssetIntegrityService


def payload(**overrides):
    base = {
        "workspace_id": "ws-a",
        "source_key": "asset-snapshot-001",
        "requested_by": "tester",
        "observations": [
            {
                "asset_id": "gateway-1",
                "asset_type": "execution-gateway",
                "criticality": 0.95,
                "inventory_coverage": 0.99,
                "ownership_coverage": 0.98,
                "baseline_compliance": 0.97,
                "configuration_integrity": 0.98,
                "patch_baseline_compliance": 0.96,
                "hardening_coverage": 0.95,
                "dependency_mapping": 0.96,
                "lifecycle_currency": 0.95,
                "backup_configuration_coverage": 0.94,
                "unauthorized_change_score": 0.02,
                "drift_score": 0.03,
                "open_configuration_findings": 0,
                "confidence": 0.98,
                "freshness": 0.99,
            }
        ],
    }
    base.update(overrides)
    return ConfigurationAssetCreate(**base)


def test_status_is_governance_only():
    service = ConfigurationAssetIntegrityService()
    status = service.status()
    assert status["governance_only"] is True
    assert status["asset_mutation_enabled"] is False
    assert status["configuration_mutation_enabled"] is False
    assert status["remediation_execution_enabled"] is False
    assert status["execution_enabled"] is False


def test_healthy_asset_scores_and_has_no_flags():
    service = ConfigurationAssetIntegrityService()
    record = service.create(payload())
    assert record.scores.aggregate_integrity > 0.85
    assert record.scores.aggregate_residual_risk < 0.20
    assert record.risk_flags == []
    assert record.dispositions[0].lifecycle_signal == "integrity-verified"


def test_drift_and_unauthorized_change_are_flagged():
    service = ConfigurationAssetIntegrityService()
    p = payload()
    observation = p.observations[0].model_copy(update={
        "drift_score": 0.55,
        "unauthorized_change_score": 0.40,
        "open_configuration_findings": 2,
    })
    p = p.model_copy(update={"observations": [observation]})
    record = service.create(p)
    assert any(flag.startswith("drift-alert:") for flag in record.risk_flags)
    assert any(flag.startswith("configuration-alert:") for flag in record.risk_flags)


def test_critical_high_risk_asset_hard_blocks():
    service = ConfigurationAssetIntegrityService()
    p = payload()
    observation = p.observations[0].model_copy(update={
        "inventory_coverage": 0.30,
        "ownership_coverage": 0.30,
        "baseline_compliance": 0.20,
        "configuration_integrity": 0.15,
        "lifecycle_currency": 0.20,
        "drift_score": 0.90,
        "unauthorized_change_score": 0.90,
    })
    record = service.create(p.model_copy(update={"observations": [observation]}))
    assert "risk-brain-hard-block" in record.risk_flags
    assert record.state.value == "blocked"


def test_findings_block_approval():
    service = ConfigurationAssetIntegrityService()
    p = payload()
    observation = p.observations[0].model_copy(update={"baseline_compliance": 0.50})
    record = service.create(p.model_copy(update={"observations": [observation]}))
    with pytest.raises(ValueError, match="findings block approval"):
        service.act("ws-a", record.record_id, "approve", "human", "op-1")


def test_human_approval_required_before_activation():
    service = ConfigurationAssetIntegrityService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.act("ws-a", record.record_id, "activate", "human", "op-1")


def test_approval_then_activation_succeeds_without_flags():
    service = ConfigurationAssetIntegrityService()
    record = service.create(payload())
    approved = service.act("ws-a", record.record_id, "approve", "risk-owner", "op-approve")
    assert approved.approved_by == "risk-owner"
    active = service.act("ws-a", record.record_id, "activate", "risk-owner", "op-activate")
    assert active.state.value == "active"


def test_replay_protection():
    service = ConfigurationAssetIntegrityService()
    record = service.create(payload())
    service.act("ws-a", record.record_id, "assess", "tester", "same-op")
    with pytest.raises(ValueError, match="operation replay detected"):
        service.act("ws-a", record.record_id, "submit-review", "tester", "same-op")


def test_workspace_isolation():
    service = ConfigurationAssetIntegrityService()
    record = service.create(payload())
    with pytest.raises(KeyError, match="record not found"):
        service.get("ws-b", record.record_id)


def test_duplicate_source_key_is_rejected_per_workspace():
    service = ConfigurationAssetIntegrityService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())
