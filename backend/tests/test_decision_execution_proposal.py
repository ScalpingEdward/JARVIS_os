import pytest
from app.schemas.decision_execution_proposal import ProposalAction,ProposalCreate
from app.services.decision_execution_proposal import DecisionExecutionProposalService

def payload(**overrides):
    action={"action_id":"a1","target":"service-x","operation":"read-config","rationale":"validated improvement","expected_outcome":"better stability","preconditions":["decision-ready"],"postconditions":["health-ok"],"rollback_plan":["restore-baseline"],"blast_radius":.2,"reversibility":.95,"observability":.95,"validation_readiness":.95}; action.update(overrides)
    return ProposalCreate(workspace_id="ws-a",source_key="proposal-1",decision_record_id="decision-1",decision_state="ready",decision_packet_digest="sha256:decision",requested_by="planner",actions=[action],decision_confidence=.95,residual_risk=.1)
def act(name,op): return ProposalAction(workspace_id="ws-a",action=name,actor="owner",operation_id=op)
def test_status_boundary():
    s=DecisionExecutionProposalService().status(); assert s["version"]=="21.126"; assert s["proposal_execution_enabled"] is False; assert s["trading_execution_enabled"] is False
def test_safe_lifecycle():
    s=DecisionExecutionProposalService(); r=s.create(payload()); assert r.state.value=="review-required"; assert r.executable is False; r=s.act(r.record_id,act("approve","op1")); r=s.act(r.record_id,act("authorize","op2")); r=s.act(r.record_id,act("prepare","op3")); assert r.state.value=="ready"; assert r.executable is False
def test_unready_decision_rejected():
    s=DecisionExecutionProposalService(); p=payload(); p.decision_state="draft"
    with pytest.raises(ValueError,match="approved/ready"): s.create(p)
def test_protected_operation_hard_blocks():
    s=DecisionExecutionProposalService(); r=s.create(payload(operation="trade-execute")); assert "risk-brain-hard-block" in r.risk_flags; assert r.state.value=="blocked"
def test_replay_and_isolation():
    s=DecisionExecutionProposalService(); r=s.create(payload()); s.act(r.record_id,act("approve","same"))
    with pytest.raises(ValueError,match="replay"): s.act(r.record_id,act("authorize","same"))
    with pytest.raises(KeyError): s.get("ws-b",r.record_id)
def test_duplicate_source_rejected():
    s=DecisionExecutionProposalService(); s.create(payload())
    with pytest.raises(ValueError,match="duplicate source_key"): s.create(payload())
