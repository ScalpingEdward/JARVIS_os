import pytest
from pydantic import ValidationError

from backend.app.modules.policy_evolution.models import PolicyChange, PolicyChangeType, PolicyEvolutionActionRequest, PolicyEvolutionCreate, PolicyEvolutionState, RiskDecision
from backend.app.modules.policy_evolution.service import PolicyEvolutionError, PolicyEvolutionService


def payload(workspace: str = "ws", source_key: str = "learning-1") -> PolicyEvolutionCreate:
    return PolicyEvolutionCreate(
        workspace_id=workspace,
        source_key=source_key,
        learning_record_id="lr-1",
        policy_domain="recovery",
        changes=[PolicyChange(change_id="c1", change_type=PolicyChangeType.THRESHOLD, policy_path="recovery.threshold", baseline_value=3, proposed_value=4, confidence=0.9, expected_impact="fewer false positives", blast_radius="recovery supervisor", rollback_condition="error rate increases", evidence_refs=["ev-1"])],
        policy_evidence_refs=["learn-1"],
    )


def act(service, record, action, **kwargs):
    return service.act(record.record_id, record.workspace_id, PolicyEvolutionActionRequest(action=action, actor="tester", **kwargs))


def move_to_review(service, record):
    act(service, record, "prepare-evidence")
    act(service, record, "evaluate")
    act(service, record, "propose", change_ids=["c1"])
    act(service, record, "request-review")


def test_full_canary_promotion_lifecycle():
    service = PolicyEvolutionService()
    record = service.create(payload())
    move_to_review(service, record)
    act(service, record, "approve", approval_token="a1")
    act(service, record, "stage", receipt_id="r1")
    act(service, record, "start-canary", receipt_id="r2")
    for index in range(3):
        act(service, record, "record-validation", receipt_id=f"v{index}", validation_healthy=True, evidence_refs=[f"e{index}"])
    act(service, record, "promote", receipt_id="p1")
    assert record.state == PolicyEvolutionState.PROMOTED


def test_unhealthy_validation_rolls_back():
    service = PolicyEvolutionService()
    record = service.create(payload())
    move_to_review(service, record)
    act(service, record, "approve", approval_token="a")
    act(service, record, "stage", receipt_id="s")
    act(service, record, "start-canary", receipt_id="c")
    act(service, record, "record-validation", receipt_id="bad", validation_healthy=False, evidence_refs=["bad-evidence"])
    assert record.state == PolicyEvolutionState.ROLLED_BACK


def test_replay_and_risk_controls():
    service = PolicyEvolutionService()
    blocked = service.create(payload("blocked", "blocked").model_copy(update={"risk_decision": RiskDecision.BLOCK}))
    act(service, blocked, "prepare-evidence")
    assert blocked.state == PolicyEvolutionState.BLOCKED
    first = service.create(payload("ws", "first"))
    second = service.create(payload("other", "second"))
    move_to_review(service, first)
    move_to_review(service, second)
    act(service, first, "approve", approval_token="unique")
    with pytest.raises(PolicyEvolutionError, match="duplicate approval token"):
        act(service, second, "approve", approval_token="unique")


def test_duplicate_change_ids_rejected():
    base = payload().model_dump()
    base["changes"] = [base["changes"][0], base["changes"][0]]
    with pytest.raises(ValidationError):
        PolicyEvolutionCreate(**base)


def test_workspace_isolation():
    service = PolicyEvolutionService()
    record = service.create(payload())
    with pytest.raises(PolicyEvolutionError):
        service.get(record.record_id, "other")
