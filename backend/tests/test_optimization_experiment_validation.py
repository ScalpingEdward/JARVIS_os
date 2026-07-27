import pytest
from app.schemas.optimization_experiment_validation import ExperimentCreate
from app.services.optimization_experiment_validation import OptimizationExperimentValidationService

def payload(**overrides):
    o={"candidate_id":"candidate-a","baseline_score":.80,"candidate_score":.90,"reliability_score":.98,"latency_score":.95,"cost_score":.95,"resource_score":.95,"shadow_coverage":.98,"ab_evidence":.98,"statistical_confidence":.98,"rollback_readiness":.98,"criticality":.7};o.update(overrides);return ExperimentCreate(workspace_id="ws-a",source_key="exp-source",requested_by="operator",observations=[o])

def test_status_disables_execution():
    s=OptimizationExperimentValidationService().status();assert s["version"]=="21.111";assert s["experiment_execution_enabled"] is False;assert s["configuration_mutation_enabled"] is False;assert s["trading_execution_enabled"] is False

def test_clean_candidate_can_be_approved_and_validated():
    s=OptimizationExperimentValidationService();r=s.create(payload());assert not r.risk_flags;r=s.act("ws-a",r.record_id,"approve","owner","op-1");r=s.act("ws-a",r.record_id,"validate","owner","op-2");assert r.state.value=="validated"

def test_regression_blocks_approval():
    s=OptimizationExperimentValidationService();r=s.create(payload(regression_count=1));assert any(x.startswith("regression-alert") for x in r.risk_flags)
    with pytest.raises(ValueError,match="findings block approval"):s.act("ws-a",r.record_id,"approve","owner","op-a")

def test_critical_failure_hard_blocks():
    s=OptimizationExperimentValidationService();r=s.create(payload(criticality=.98,reliability_score=.05,statistical_confidence=.20,ab_evidence=.20,rollback_readiness=.10,regression_count=3));assert "risk-brain-hard-block" in r.risk_flags;assert r.state.value=="blocked"

def test_replay_workspace_and_duplicate_guards():
    s=OptimizationExperimentValidationService();r=s.create(payload());s.act("ws-a",r.record_id,"assess","reviewer","same")
    with pytest.raises(ValueError,match="replay"):s.act("ws-a",r.record_id,"submit-review","reviewer","same")
    with pytest.raises(KeyError):s.get("ws-b",r.record_id)
    with pytest.raises(ValueError,match="duplicate source_key"):s.create(payload())
