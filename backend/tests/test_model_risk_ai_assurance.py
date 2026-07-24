import pytest

from app.schemas.model_risk_ai_assurance import ModelRiskAssuranceCreate, ModelObservation
from app.services.model_risk_ai_assurance import ModelRiskAIAssuranceService


def observation(**overrides):
    data = {
        "model_id": "portfolio-brain",
        "model_version": "21.77",
        "model_type": "decision-synthesis",
        "business_criticality": 0.9,
        "validation_coverage": 0.92,
        "performance_stability": 0.88,
        "calibration_quality": 0.86,
        "explainability_coverage": 0.84,
        "fairness_score": 0.91,
        "data_quality_score": 0.90,
        "drift_score": 0.08,
        "robustness_score": 0.87,
        "fallback_readiness": 0.89,
        "human_oversight_coverage": 1.0,
        "confidence": 0.95,
        "freshness": 0.98,
        "provenance": ["validation-report", "monitoring-snapshot"],
    }
    data.update(overrides)
    return ModelObservation(**data)


def payload(**overrides):
    data = {
        "workspace_id": "alpha",
        "source_key": "assurance-2026-07-23",
        "observations": [observation()],
        "requested_by": "model-risk-officer",
    }
    data.update(overrides)
    return ModelRiskAssuranceCreate(**data)


def test_assessment_produces_assurance_scores():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload())
    assessed = service.act("alpha", record.record_id, "assess", "validator", "op-1")
    assert assessed.scores.aggregate_assurance > 0.75
    assert assessed.scores.aggregate_residual_risk < 0.35
    assert assessed.dispositions[0].lifecycle_signal == "assured"


def test_drift_bias_and_explainability_alerts_are_detected():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload(observations=[observation(
        drift_score=0.62,
        fairness_score=0.55,
        explainability_coverage=0.40,
        data_quality_score=0.60,
    )]))
    assert any(flag.startswith("drift-alert") for flag in record.risk_flags)
    assert any(flag.startswith("bias-alert") for flag in record.risk_flags)
    assert any(flag.startswith("explainability-gap") for flag in record.risk_flags)
    assert any(flag.startswith("data-quality-alert") for flag in record.risk_flags)


def test_unresolved_flags_block_approval():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload(observations=[observation(validation_coverage=0.50)]))
    service.act("alpha", record.record_id, "assess", "validator", "op-1")
    service.act("alpha", record.record_id, "submit-review", "validator", "op-2")
    with pytest.raises(ValueError, match="unresolved model-risk flags"):
        service.act("alpha", record.record_id, "approve", "human", "op-3")


def test_human_approval_required_before_activation():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload())
    with pytest.raises(ValueError, match="human approval required"):
        service.act("alpha", record.record_id, "activate", "operator", "op-1")


def test_operation_replay_is_rejected():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload())
    service.act("alpha", record.record_id, "assess", "validator", "same-op")
    with pytest.raises(ValueError, match="replay"):
        service.act("alpha", record.record_id, "submit-review", "validator", "same-op")


def test_workspace_isolation():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload())
    with pytest.raises(KeyError):
        service.get("other-workspace", record.record_id)


def test_duplicate_source_key_is_rejected():
    service = ModelRiskAIAssuranceService()
    service.create(payload())
    with pytest.raises(ValueError, match="duplicate source_key"):
        service.create(payload())


def test_critical_high_risk_model_triggers_risk_brain_hard_block():
    service = ModelRiskAIAssuranceService()
    record = service.create(payload(observations=[observation(
        business_criticality=0.98,
        validation_coverage=0.10,
        performance_stability=0.20,
        explainability_coverage=0.20,
        fairness_score=0.30,
        data_quality_score=0.30,
        drift_score=0.90,
        fallback_readiness=0.10,
        open_validation_findings=8,
    )]))
    assert record.state.value == "blocked"
    assert "risk-brain-hard-block" in record.risk_flags


def test_status_preserves_advisory_only_boundary():
    status = ModelRiskAIAssuranceService().status()
    assert status["model_mutation_enabled"] is False
    assert status["deployment_mutation_enabled"] is False
    assert status["portfolio_mutation_enabled"] is False
    assert status["execution_enabled"] is False
