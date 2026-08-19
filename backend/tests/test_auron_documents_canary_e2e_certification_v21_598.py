from dataclasses import replace
import pytest

from app.core.auron_integration_readiness_v21_598 import get_integration_readiness
from app.core.auron_production_readiness_canary_gate_v21_583 import CanaryReadinessDecision
from app.documents.auron_documents_canary_e2e_certification_v21_598 import (
    DocumentsCanaryE2ECertificationError,DocumentsCanaryE2ECertificationHarness,DocumentsCanaryE2ERequest)


def ready():
    return CanaryReadinessDecision('d-documents','files-documents','documents-local-readonly',True,(),1,True,False,
        '2026-08-19T10:00:00+00:00','evidence-documents')


def request(**overrides):
    values=dict(readiness_decision=ready(),operator_id='operator-1',scope='metadata-only',
        action_key='inspect-file-metadata',payload={'file_id':'file-1'})
    values.update(overrides); return DocumentsCanaryE2ERequest(**values)


def test_full_documents_chain_certifies_with_zero_mutation_and_transport(tmp_path):
    r=DocumentsCanaryE2ECertificationHarness(tmp_path).run(request())
    assert r.execution_state=='provider-submitted' and r.reconciliation_state=='reconciled'
    assert r.certification_outcome=='promote' and r.certified is True
    assert r.read_only is True and r.mutation_enabled is False and r.delete_enabled is False and r.move_enabled is False
    assert r.network_transport_enabled is False and r.production_transport_enabled is False and r.external_calls_made==0


def test_same_request_is_idempotent_across_execution_and_reconciliation(tmp_path):
    h=DocumentsCanaryE2ECertificationHarness(tmp_path); a=h.run(request()); b=h.run(request())
    assert a.activation_id==b.activation_id and a.execution_id==b.execution_id
    assert a.reconciliation_id==b.reconciliation_id and a.certification_id==b.certification_id


def test_wrong_provider_fails_before_execution(tmp_path):
    bad=replace(ready(),provider_id='documents-live-provider')
    with pytest.raises(DocumentsCanaryE2ECertificationError):
        DocumentsCanaryE2ECertificationHarness(tmp_path).run(request(readiness_decision=bad))


def test_mutation_action_fails_before_execution(tmp_path):
    with pytest.raises(DocumentsCanaryE2ECertificationError):
        DocumentsCanaryE2ECertificationHarness(tmp_path).run(request(action_key='delete-file'))


def test_version_preview_certifies_without_content_read(tmp_path):
    r=DocumentsCanaryE2ECertificationHarness(tmp_path).run(request(
        action_key='preview-file-version',scope='version-preview',payload={'file_id':'file-1','version_id':'v2'}))
    assert r.certified is True and r.external_calls_made==0 and r.mutation_enabled is False


def test_health_or_approval_drift_yields_hold(tmp_path):
    a=DocumentsCanaryE2ECertificationHarness(tmp_path/'a').run(request(provider_health_green=False))
    b=DocumentsCanaryE2ECertificationHarness(tmp_path/'b').run(request(operator_promotion_approved=False))
    assert a.certification_outcome=='hold' and a.certified is False
    assert b.certification_outcome=='hold' and b.certified is False


def test_g11_readiness_advances_to_g12():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.598'
    assert r['next_item']=='G12-documents-health-drift-command-centre-certification'
    assert r['live_transports_enabled'] is False and r['trading_execution_enabled'] is False
