from dataclasses import replace
import pytest

from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision
from app.research.auron_research_canary_e2e_certification_v21_589 import (
    ResearchCanaryE2ECertificationError, ResearchCanaryE2ECertificationHarness,
    ResearchCanaryE2ERequest)
from app.core.auron_integration_readiness_v21_589 import get_integration_readiness


def ready():
    return CanaryReadinessDecision(
        'd-research','research','research-local-readonly',True,(),1,True,False,
        '2026-08-18T19:00:00+00:00','evidence-research')


def request(**overrides):
    values=dict(readiness_decision=ready(),operator_id='operator-1',scope='preview-only',
        action_key='search-preview',payload={'query':'gold macro outlook'})
    values.update(overrides); return ResearchCanaryE2ERequest(**values)


def test_full_research_canary_chain_certifies_without_production_transport(tmp_path):
    result=ResearchCanaryE2ECertificationHarness(tmp_path).run(request())
    assert result.execution_state=='provider-submitted'
    assert result.reconciliation_state=='reconciled'
    assert result.certification_outcome=='promote' and result.certified is True
    assert result.production_transport_enabled is False and result.network_transport_enabled is False


def test_same_request_is_idempotent_across_execution_and_reconciliation(tmp_path):
    harness=ResearchCanaryE2ECertificationHarness(tmp_path)
    a=harness.run(request()); b=harness.run(request())
    assert a.activation_id==b.activation_id
    assert a.execution_id==b.execution_id
    assert a.reconciliation_id==b.reconciliation_id
    assert a.certification_id==b.certification_id


def test_wrong_provider_fails_before_execution(tmp_path):
    bad=replace(ready(),provider_id='other-provider')
    with pytest.raises(ResearchCanaryE2ECertificationError):
        ResearchCanaryE2ECertificationHarness(tmp_path).run(request(readiness_decision=bad))


def test_disallowed_action_fails_before_execution(tmp_path):
    with pytest.raises(ResearchCanaryE2ECertificationError):
        ResearchCanaryE2ECertificationHarness(tmp_path).run(request(action_key='write-result'))


def test_health_drift_yields_hold_not_production_enablement(tmp_path):
    result=ResearchCanaryE2ECertificationHarness(tmp_path).run(request(provider_health_green=False))
    assert result.certification_outcome=='hold' and result.certified is False
    assert result.production_transport_enabled is False


def test_g2_readiness_advances_to_g3():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.589'
    assert r['next_item']=='G3-research-provider-health-drift-certification'
    assert r['live_transports_enabled'] is False
