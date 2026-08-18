from types import SimpleNamespace
import pytest

from app.core.auron_canary_certification_promotion_rollback_v21_587 import (
    CanaryCertificationEvidence, CanaryCertificationError,
    CanaryCertificationPromotionRollbackService,
)
from app.core.auron_integration_readiness_v21_587 import get_integration_readiness


class Executions:
    def __init__(self, records): self.records=records
    def list_for_activation(self, activation_id): return tuple(self.records)

class Reconciliation:
    def __init__(self, mapping): self.mapping=mapping
    def get_by_execution(self, execution_id): return self.mapping.get(execution_id)


def execution(eid='e1'):
    return SimpleNamespace(execution_id=eid,state='provider-submitted')

def rec(ok=True,stop=False,state=None):
    return SimpleNamespace(progression_authorized=ok,stop_required=stop,state=state or ('reconciled' if ok else 'stopped'))

def evidence(**overrides):
    values=dict(activation_id='a1',vertical='research',provider_id='p',operator_id='op',
        all_submitted_actions_reconciled=True,any_stop_required=False,any_stop_failed=False,
        kill_switch_available=True,reconciliation_available=True,rollback_control_available=True,
        provider_health_green=True,policy_green=True,operator_promotion_approved=True,
        requested_outcome='promote')
    values.update(overrides); return CanaryCertificationEvidence(**values)


def test_clean_reconciled_canary_can_be_certified_for_promotion():
    s=CanaryCertificationPromotionRollbackService(Executions([execution()]),Reconciliation({'e1':rec()}))
    d=s.evaluate(evidence())
    assert d.certified is True and d.outcome=='promote'
    assert d.unrestricted_production_enabled_by_decision is False
    assert s.require_promotion_authorized(d)==d


def test_stop_forces_rollback_even_when_promotion_requested():
    s=CanaryCertificationPromotionRollbackService(Executions([execution()]),Reconciliation({'e1':rec(False,True,'stopped')}))
    d=s.evaluate(evidence(all_submitted_actions_reconciled=False,any_stop_required=True))
    assert d.outcome=='rollback' and d.rollback_required is True
    assert d.unrestricted_production_enabled_by_decision is False


def test_stop_failure_forces_rollback_and_blocks_promotion():
    s=CanaryCertificationPromotionRollbackService(Executions([execution()]),Reconciliation({'e1':rec(False,True,'stop-failed')}))
    d=s.evaluate(evidence(all_submitted_actions_reconciled=False,any_stop_required=True,any_stop_failed=True))
    assert d.outcome=='rollback' and 'canary-stop-failed' in d.blockers
    with pytest.raises(CanaryCertificationError): s.require_promotion_authorized(d)


def test_missing_explicit_promotion_approval_holds():
    s=CanaryCertificationPromotionRollbackService(Executions([execution()]),Reconciliation({'e1':rec()}))
    d=s.evaluate(evidence(operator_promotion_approved=False))
    assert d.outcome=='hold' and d.certified is False


def test_health_or_policy_drift_blocks_promotion():
    s=CanaryCertificationPromotionRollbackService(Executions([execution()]),Reconciliation({'e1':rec()}))
    d=s.evaluate(evidence(provider_health_green=False,policy_green=False))
    assert d.outcome=='hold'
    assert {'provider-health-not-green','policy-not-green'} <= set(d.blockers)


def test_f4_completes_phase_f_and_keeps_production_disabled():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.587'
    assert r['next_item']=='G1-provider-specific-canary-adapter-selection'
    assert r['unrestricted_production_transport_enabled'] is False
