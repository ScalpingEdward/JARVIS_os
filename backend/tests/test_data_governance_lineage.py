import pytest

from app.schemas.data_governance_lineage import DataAssetObservation, DataGovernanceCreate, DataGovernanceState
from app.services.data_governance_lineage import DataGovernanceLineageService


def healthy_payload(source_key: str = "feed:alpha") -> DataGovernanceCreate:
    return DataGovernanceCreate(
        workspace_id="ws-1",
        source_key=source_key,
        requested_by="risk-ops",
        observations=[
            DataAssetObservation(
                asset_id="market-data.gold.tick",
                asset_type="market-data",
                owner="market-data-owner",
                steward="data-steward",
                criticality=0.85,
                lineage_coverage=0.96,
                source_authority=0.95,
                schema_integrity=0.98,
                completeness=0.97,
                accuracy=0.96,
                freshness=0.95,
                timeliness=0.94,
                access_control_coverage=0.98,
                retention_compliance=0.96,
                pii_exposure_risk=0.01,
                unresolved_quality_issues=0,
                downstream_dependencies=8,
                confidence=0.95,
            )
        ],
    )


def test_status_is_advisory_only() -> None:
    service = DataGovernanceLineageService()
    status = service.status()
    assert status["governance_only"] is True
    assert status["data_mutation_enabled"] is False
    assert status["schema_mutation_enabled"] is False
    assert status["access_policy_mutation_enabled"] is False
    assert status["execution_enabled"] is False


def test_healthy_asset_scores_as_trusted() -> None:
    service = DataGovernanceLineageService()
    record = service.create(healthy_payload())
    assert record.state == DataGovernanceState.EVIDENCE_READY
    assert record.risk_flags == []
    assert record.dispositions[0].lifecycle_signal == "trusted"
    assert record.scores.aggregate_trust > 0.80


def test_lineage_quality_and_access_alerts_are_detected() -> None:
    service = DataGovernanceLineageService()
    payload = healthy_payload("feed:degraded")
    degraded = payload.observations[0].model_copy(update={
        "lineage_coverage": 0.45,
        "accuracy": 0.55,
        "unresolved_quality_issues": 3,
        "access_control_coverage": 0.50,
        "pii_exposure_risk": 0.55,
    })
    payload = payload.model_copy(update={"observations": [degraded]})
    record = service.create(payload)
    assert any(flag.startswith("lineage-gap:") for flag in record.risk_flags)
    assert any(flag.startswith("quality-alert:") for flag in record.risk_flags)
    assert any(flag.startswith("access-alert:") for flag in record.risk_flags)
    with pytest.raises(ValueError, match="flags block approval"):
        service.act("ws-1", record.record_id, "approve", "human", "op-approve")


def test_critical_high_risk_asset_triggers_risk_brain_hard_block() -> None:
    service = DataGovernanceLineageService()
    payload = healthy_payload("feed:critical")
    critical = payload.observations[0].model_copy(update={
        "criticality": 0.99,
        "lineage_coverage": 0.10,
        "completeness": 0.20,
        "accuracy": 0.20,
        "freshness": 0.20,
        "access_control_coverage": 0.10,
        "pii_exposure_risk": 0.90,
        "retention_compliance": 0.20,
    })
    payload = payload.model_copy(update={"observations": [critical]})
    record = service.create(payload)
    assert record.state == DataGovernanceState.BLOCKED
    assert "risk-brain-hard-block" in record.risk_flags


def test_human_approval_required_before_activation() -> None:
    service = DataGovernanceLineageService()
    record = service.create(healthy_payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.act("ws-1", record.record_id, "activate", "operator", "op-activate-early")
    approved = service.act("ws-1", record.record_id, "approve", "human", "op-approve")
    active = service.act("ws-1", approved.record_id, "activate", "operator", "op-activate")
    assert active.state == DataGovernanceState.ACTIVE
    assert approved.approved_by == "human"


def test_replay_and_workspace_isolation() -> None:
    service = DataGovernanceLineageService()
    record = service.create(healthy_payload())
    service.act("ws-1", record.record_id, "assess", "operator", "op-1")
    with pytest.raises(ValueError, match="replay"):
        service.act("ws-1", record.record_id, "submit-review", "operator", "op-1")
    with pytest.raises(KeyError, match="record not found"):
        service.get("ws-2", record.record_id)


def test_duplicate_source_key_is_blocked_and_audit_is_workspace_scoped() -> None:
    service = DataGovernanceLineageService()
    record = service.create(healthy_payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(healthy_payload())
    audit = service.audit("ws-1")
    assert len(audit) == 1
    assert audit[0].record_id == record.record_id
    assert service.audit("ws-2") == []
