from dataclasses import replace
import pytest

from app.communications.auron_communications_canary_e2e_certification_v21_602 import (
    CommunicationsCanaryE2ECertificationError,CommunicationsCanaryE2ECertificationHarness,
    CommunicationsCanaryE2ERequest)
from app.core.auron_integration_readiness_v21_602 import get_integration_readiness
from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision


def ready():
    return CanaryReadinessDecision('d-communications','communications','communications-local-draft',True,(),1,True,False,
        '2026-08-19T10:50:00+00:00','evidence-communications')


def request(**overrides):
    values=dict(readiness_decision=ready(),operator_id='operator-1',scope='message-preview-only',
        action_key='render-message-preview',payload={'draft_id':'draft-1','body':'hello world','recipient_refs':['r1']})
    values.update(overrides); return CommunicationsCanaryE2ERequest(**values)


def test_full_communications_chain_certifies_with_zero_send_and_transport(tmp_path):
    r=CommunicationsCanaryE2ECertificationHarness(tmp_path).run(request())
    assert r.execution_state=='provider-submitted' and r.reconciliation_state=='reconciled'
    assert r.certification_outcome=='promote' and r.certified is True
    assert r.outbound_send_enabled is False and r.provider_write_enabled is False
    assert r.network_transport_enabled is False and r.production_transport_enabled is False
    assert r.network_calls_made==0


def test_same_request_is_idempotent_across_execution_and_reconciliation(tmp_path):
    h=CommunicationsCanaryE2ECertificationHarness(tmp_path); a=h.run(request()); b=h.run(request())
    assert a.activation_id==b.activation_id and a.execution_id==b.execution_id
    assert a.reconciliation_id==b.reconciliation_id and a.certification_id==b.certification_id


def test_wrong_provider_fails_before_execution(tmp_path):
    bad=replace(ready(),provider_id='communications-live-provider')
    with pytest.raises(CommunicationsCanaryE2ECertificationError):
        CommunicationsCanaryE2ECertificationHarness(tmp_path).run(request(readiness_decision=bad))


def test_send_action_fails_before_execution(tmp_path):
    with pytest.raises(CommunicationsCanaryE2ECertificationError):
        CommunicationsCanaryE2ECertificationHarness(tmp_path).run(request(action_key='send-message'))


def test_recipient_plan_certifies_without_delivery(tmp_path):
    r=CommunicationsCanaryE2ECertificationHarness(tmp_path).run(request(
        action_key='inspect-recipient-plan',scope='recipient-plan-only',
        payload={'draft_id':'draft-1','recipient_refs':['r1','r2']}))
    assert r.certified is True and r.outbound_send_enabled is False and r.network_calls_made==0


def test_health_or_approval_drift_yields_hold(tmp_path):
    a=CommunicationsCanaryE2ECertificationHarness(tmp_path/'a').run(request(provider_health_green=False))
    b=CommunicationsCanaryE2ECertificationHarness(tmp_path/'b').run(request(operator_promotion_approved=False))
    assert a.certification_outcome=='hold' and a.certified is False
    assert b.certification_outcome=='hold' and b.certified is False


def test_g15_readiness_advances_to_g16():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.602'
    assert r['next_item']=='G16-communications-health-drift-command-centre-certification'
    assert r['live_transports_enabled'] is False and r['trading_execution_enabled'] is False
