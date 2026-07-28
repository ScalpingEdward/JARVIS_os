import pytest
from app.services.baseline_impact_simulation import BaselineImpactSimulationService


def baseline(**overrides):
    value = {
        "baseline_id": "base-1", "workspace_id": "ws-1", "status": "active",
        "human_approved": True, "risk_brain_blocked": False,
        "version": 3, "baseline_value": 0.82,
    }
    value.update(overrides)
    return value


def scenarios():
    return [
        {
            "scenario_id": "s1", "candidate_id": "adapter-a", "current_score": 0.80,
            "baseline_sensitivity": 0.2, "reference_baseline": 0.80,
            "current_rank": 1, "simulated_rank": 1,
            "failover_trigger_before": False, "failover_trigger_after": False,
            "recovery_ready_before": True, "recovery_ready_after": True,
        },
        {
            "scenario_id": "s2", "candidate_id": "adapter-b", "current_score": 0.72,
            "baseline_sensitivity": 0.1, "reference_baseline": 0.80,
            "current_rank": 2, "simulated_rank": 2,
            "failover_trigger_before": False, "failover_trigger_after": False,
            "recovery_ready_before": True, "recovery_ready_after": True,
        },
    ]


def test_clean_preview_requires_human_approval():
    svc = BaselineImpactSimulationService()
    rec = svc.simulate(record_id="r1", workspace_id="ws-1", active_baseline=baseline(), scenarios=scenarios(), source_key="k1")
    assert rec.status == "review-required"
    with pytest.raises(ValueError):
        svc.approve("r1", human_approved=False)
    assert svc.approve("r1", human_approved=True).status == "approved-preview"


def test_inactive_baseline_blocks():
    svc = BaselineImpactSimulationService()
    rec = svc.simulate(record_id="r2", workspace_id="ws-1", active_baseline=baseline(status="proposed"), scenarios=scenarios(), source_key="k2")
    assert rec.status == "blocked"
    assert "baseline-not-active" in rec.findings


def test_large_behavior_change_blocks():
    svc = BaselineImpactSimulationService()
    changed = scenarios()
    changed[0]["simulated_rank"] = 2
    changed[0]["failover_trigger_after"] = True
    changed[0]["recovery_ready_after"] = False
    rec = svc.simulate(record_id="r3", workspace_id="ws-1", active_baseline=baseline(), scenarios=changed, source_key="k3")
    assert rec.status == "blocked"
    assert "blast-radius-above-preview-threshold" in rec.findings


def test_risk_brain_block_propagates():
    svc = BaselineImpactSimulationService()
    rec = svc.simulate(record_id="r4", workspace_id="ws-1", active_baseline=baseline(risk_brain_blocked=True), scenarios=scenarios(), source_key="k4")
    assert rec.risk_brain_blocked
    assert rec.status == "blocked"


def test_replay_and_workspace_isolation():
    svc = BaselineImpactSimulationService()
    svc.simulate(record_id="r5", workspace_id="ws-1", active_baseline=baseline(), scenarios=scenarios(), source_key="same")
    with pytest.raises(ValueError):
        svc.simulate(record_id="r6", workspace_id="ws-1", active_baseline=baseline(), scenarios=scenarios(), source_key="same")
    rec = svc.simulate(record_id="r7", workspace_id="ws-2", active_baseline=baseline(), scenarios=scenarios(), source_key="same")
    assert rec.status == "blocked"
    assert "workspace-mismatch" in rec.findings
