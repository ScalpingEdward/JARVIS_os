from types import SimpleNamespace
import pytest

from app.core.auron_canary_reconciliation_stop_enforcement_v21_586 import (
    CanaryProviderResult, CanaryReconciliationError, CanaryReconciliationStopService)
from app.core.auron_integration_readiness_v21_586 import get_integration_readiness


class Executions:
    def __init__(self,records=()): self.records=records
    def list_for_activation(self,a): return tuple(self.records)
class Reader:
    def __init__(self,result=None,error=False): self.result=result; self.error=error
    def read_result(self,**kwargs):
        if self.error: raise RuntimeError('missing')
        return self.result
class Stopper:
    def __init__(self,error=False): self.calls=[]; self.error=error
    def stop_canary(self,**kwargs):
        self.calls.append(kwargs)
        if self.error: raise RuntimeError('stop failed')

def execution():
    return SimpleNamespace(execution_id='canary-exec-abc',activation_id='auth1',vertical='research',provider_id='p',action_key='read',payload_hash='hash',state='provider-submitted',provider_ref='ref')
def good(): return CanaryProviderResult('ref','research','p','succeeded','read','hash')

def test_successful_result_allows_progression(tmp_path):
    e=execution(); s=CanaryReconciliationStopService(tmp_path/'r.db',Executions([e]),Reader(good()),Stopper())
    r=s.reconcile(e,kill_switch_active=True,reconciliation_ready=True,stop_control_ready=True)
    assert r.state=='reconciled' and r.progression_authorized is True and r.stop_required is False
    assert s.activation_progression_ready('auth1') is True

def test_payload_mismatch_forces_stop_and_blocks_progression(tmp_path):
    e=execution(); bad=CanaryProviderResult('ref','research','p','succeeded','read','different'); stop=Stopper()
    s=CanaryReconciliationStopService(tmp_path/'r.db',Executions([e]),Reader(bad),stop)
    r=s.reconcile(e,kill_switch_active=True,reconciliation_ready=True,stop_control_ready=True)
    assert r.state=='stopped' and r.stop_enforced is True and r.progression_authorized is False
    assert 'payload-hash-mismatch' in r.blockers and len(stop.calls)==1

def test_missing_result_forces_stop(tmp_path):
    e=execution(); stop=Stopper(); s=CanaryReconciliationStopService(tmp_path/'r.db',Executions([e]),Reader(error=True),stop)
    r=s.reconcile(e,kill_switch_active=True,reconciliation_ready=True,stop_control_ready=True)
    assert 'provider-result-missing-or-read-failed' in r.blockers and r.stop_enforced is True

def test_safety_drift_forces_stop_without_result_read(tmp_path):
    e=execution(); stop=Stopper(); s=CanaryReconciliationStopService(tmp_path/'r.db',Executions([e]),Reader(good()),stop)
    r=s.reconcile(e,kill_switch_active=False,reconciliation_ready=True,stop_control_ready=True)
    assert 'kill-switch-drift' in r.blockers and r.progression_authorized is False

def test_stop_failure_is_fail_closed(tmp_path):
    e=execution(); bad=CanaryProviderResult('ref','research','p','failed','read','hash')
    s=CanaryReconciliationStopService(tmp_path/'r.db',Executions([e]),Reader(bad),Stopper(error=True))
    r=s.reconcile(e,kill_switch_active=True,reconciliation_ready=True,stop_control_ready=True)
    assert r.state=='stop-failed' and r.progression_authorized is False and 'stop-enforcement-failed' in r.blockers
    with pytest.raises(CanaryReconciliationError): s.require_progression(e.execution_id)

def test_f3_readiness_advances_to_f4():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.586'
    assert r['next_item']=='F4-canary-certification-promotion-rollback-decision'
    assert r['live_transports_enabled'] is False
