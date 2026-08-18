import pytest

from app.core.auron_controlled_canary_execution_boundary_v21_585 import CanaryExecutionRequest, ControlledCanaryExecutionError, ControlledCanaryExecutionService
from app.core.auron_controlled_provider_canary_contract_v21_584 import CanaryActivationDecision
from app.core.auron_integration_readiness_v21_585 import get_integration_readiness


def auth(actions=2):
    return CanaryActivationDecision('a1','d1','research','p','op','scope',actions,True,(),False,'hash')


class Transport:
    def __init__(self): self.calls=[]
    def execute_canary_action(self, **kwargs):
        self.calls.append(kwargs)
        return 'provider-ref-' + str(len(self.calls))


def test_default_transport_is_disabled(tmp_path):
    s=ControlledCanaryExecutionService(tmp_path/'c.sqlite3')
    r=s.execute(CanaryExecutionRequest(auth(),'x',{'a':1},True,True,True))
    assert r.state=='transport-disabled'
    assert r.external_calls_made==0


def test_authorized_transport_submission_is_idempotent(tmp_path):
    t=Transport(); s=ControlledCanaryExecutionService(tmp_path/'c.sqlite3',t)
    req=CanaryExecutionRequest(auth(),'x',{'a':1},True,True,True)
    a=s.execute(req); b=s.execute(req)
    assert a.execution_id==b.execution_id
    assert a.state=='provider-submitted'
    assert len(t.calls)==1


def test_hard_budget_blocks_third_unique_action(tmp_path):
    t=Transport(); s=ControlledCanaryExecutionService(tmp_path/'c.sqlite3',t)
    s.execute(CanaryExecutionRequest(auth(2),'a',{'n':1},True,True,True))
    s.execute(CanaryExecutionRequest(auth(2),'b',{'n':2},True,True,True))
    third=s.execute(CanaryExecutionRequest(auth(2),'c',{'n':3},True,True,True))
    assert third.state=='blocked'
    assert 'canary-action-budget-exhausted' in third.blockers
    assert len(t.calls)==2


def test_each_action_rechecks_safety_controls(tmp_path):
    t=Transport(); s=ControlledCanaryExecutionService(tmp_path/'c.sqlite3',t)
    r=s.execute(CanaryExecutionRequest(auth(),'x',{},False,False,False))
    assert r.state=='blocked'
    assert {'kill-switch-not-active','reconciliation-not-ready','stop-control-not-ready'} <= set(r.blockers)
    assert len(t.calls)==0


def test_invalid_f1_authorization_is_rejected(tmp_path):
    bad=CanaryActivationDecision('a','d','research','p','op','scope',1,False,('x',),False,'h')
    with pytest.raises(ControlledCanaryExecutionError):
        ControlledCanaryExecutionService(tmp_path/'c.sqlite3').execute(CanaryExecutionRequest(bad,'x',{},True,True,True))


def test_f2_readiness_advances_to_reconciliation_stop():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.585'
    assert r['next_item']=='F3-canary-result-reconciliation-stop-enforcement'
    assert r['live_transports_enabled'] is False
