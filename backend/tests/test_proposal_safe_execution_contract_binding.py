import pytest
from app.schemas.proposal_safe_execution_contract_binding import ExecutionBindingAction, ExecutionBindingCreate
from app.services.proposal_safe_execution_contract_binding import ProposalSafeExecutionContractBindingService

def payload(**overrides):
    data={"workspace_id":"ws-a","source_key":"bind-001","requested_by":"orchestrator","proposal_record_id":"proposal-1","proposal_digest":"sha256:proposal","proposal_state":"authorized","proposal_authorized":True,"safe_execution_contract_id":"contract-1","safe_execution_contract_digest":"sha256:contract","sandbox_policy_id":"sandbox-1","adapter_policy_id":"adapter-1","gateway_policy_id":"gateway-1","worker_policy_id":"worker-1","operation":"read-repository","target":"api.github.com/repos/ScalpingEdward/JARVIS_os"}
    data.update(overrides); return ExecutionBindingCreate(**data)

def action(name,op): return ExecutionBindingAction(workspace_id="ws-a",action=name,actor="owner",operation_id=op)

def test_status_disables_execution_and_bypass():
    s=ProposalSafeExecutionContractBindingService().status(); assert s["version"]=="21.127"; assert s["execution_enabled"] is False; assert s["sandbox_bypass_enabled"] is False; assert s["gateway_bypass_enabled"] is False

def test_safe_binding_lifecycle():
    s=ProposalSafeExecutionContractBindingService(); r=s.create(payload()); assert not r.risk_flags; r=s.act(r.record_id,action("approve","op1")); r=s.act(r.record_id,action("bind","op2")); r=s.act(r.record_id,action("mark-ready","op3")); assert r.state.value=="ready"; assert r.execution_enabled is False

def test_protected_operation_hard_blocks():
    s=ProposalSafeExecutionContractBindingService(); r=s.create(payload(operation="trade-execute")); assert "risk-brain-hard-block" in r.risk_flags; assert r.state.value=="blocked"

def test_direct_execution_request_hard_blocks():
    s=ProposalSafeExecutionContractBindingService(); r=s.create(payload(execution_enabled=True)); assert "direct-execution-requested" in r.risk_flags; assert "risk-brain-hard-block" in r.risk_flags

def test_unauthorized_proposal_blocks_approval():
    s=ProposalSafeExecutionContractBindingService(); r=s.create(payload(proposal_authorized=False)); assert "proposal-not-authorized" in r.risk_flags
    with pytest.raises(ValueError,match="findings block approval"): s.act(r.record_id,action("approve","opx"))

def test_replay_isolation_and_duplicate_source():
    s=ProposalSafeExecutionContractBindingService(); r=s.create(payload()); s.act(r.record_id,action("approve","same"))
    with pytest.raises(ValueError,match="replay"): s.act(r.record_id,action("bind","same"))
    with pytest.raises(KeyError): s.get("ws-b",r.record_id)
    with pytest.raises(ValueError,match="duplicate source_key"): s.create(payload())
