from dataclasses import replace
from datetime import datetime,timedelta,timezone

from app.core.auron_external_provider_contract_registry_v21_609 import ExternalProviderContractRegistry
from app.research.auron_research_external_readonly_sandbox_adapter_v21_610 import ResearchExternalReadonlySandboxAdapter
from app.research.auron_research_external_sandbox_e2e_reconciliation_v21_611 import ResearchExternalSandboxE2EReconciler
from app.research.auron_research_external_sandbox_health_drift_observability_v21_612 import ResearchExternalSandboxHealthDriftObservability
from app.core.auron_integration_readiness_v21_612 import get_integration_readiness


def build(tmp_path,max_age=300):
    r=ExternalProviderContractRegistry(tmp_path/'contracts.db')
    c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',allowed_capabilities=('search-readonly','inspect-source-metadata'),credential_ref='secretref://research/sandbox/read-only')
    a=ResearchExternalReadonlySandboxAdapter(tmp_path/'adapter.db',r,c.contract_id)
    x=ResearchExternalSandboxE2EReconciler(tmp_path/'reconcile.db',r,a)
    ref=a.execute_canary_action(vertical='research',provider_id='research-external-readonly-sandbox',scope='health',action_key='search-readonly',payload={'query':'rates'},idempotency_key='h4-1')
    cert=x.certify(contract_id=c.contract_id,provider_ref=ref,action_key='search-readonly')
    h=ResearchExternalSandboxHealthDriftObservability(tmp_path/'health.db',r,a,x,max_age_seconds=max_age)
    return r,c,a,x,cert,h


def test_fresh_healthy_snapshot_is_operationally_ready_but_transport_stays_off(tmp_path):
    r,c,a,x,cert,h=build(tmp_path); now=datetime.now(timezone.utc)
    h.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=True,observed_at=now.isoformat())
    s=h.snapshot(now=(now+timedelta(seconds=5)).isoformat())
    assert s['operationally_ready'] is True and s['blockers']==()
    assert s['network_transport_enabled'] is False and s['provider_write_enabled'] is False
    assert s['credential_resolution_enabled'] is False and s['production_transport_enabled'] is False


def test_stale_and_unhealthy_health_fail_closed(tmp_path):
    r,c,a,x,cert,h=build(tmp_path,60); now=datetime.now(timezone.utc)
    h.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=False,observed_at=(now-timedelta(seconds=61)).isoformat())
    s=h.snapshot(now=now.isoformat())
    assert s['operationally_ready'] is False
    assert {'provider-unhealthy','health-evidence-stale'} <= set(s['blockers'])


def test_adapter_drift_is_detected(tmp_path):
    r,c,a,x,cert,h=build(tmp_path); h.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=True)
    original=a.descriptor; a.descriptor=lambda: replace(original(),network_transport_enabled=True)
    s=h.snapshot(); assert s['operationally_ready'] is False and s['drift_detected'] is True and 'adapter-drift' in s['blockers']


def test_contract_drift_is_detected(tmp_path):
    r,c,a,x,cert,h=build(tmp_path); h.record(contract_id=c.contract_id,certification_id=cert.certification_id,healthy=True)
    original=h.contract_fingerprint; h.contract_fingerprint=lambda contract_id: 'changed'
    s=h.snapshot(); assert s['operationally_ready'] is False and 'contract-drift' in s['blockers']
    h.contract_fingerprint=original


def test_missing_health_is_visible_and_fail_closed(tmp_path):
    r,c,a,x,cert,h=build(tmp_path); s=h.snapshot()
    assert s['operationally_ready'] is False and 'health-evidence-missing' in s['blockers']


def test_h4_readiness_advances_to_h5_without_transport():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.612'
    assert r['next_item']=='H5-explicit-network-transport-authorization-decision'
    assert r['external_provider_network_enabled'] is False and r['external_provider_write_enabled'] is False
    assert r['external_provider_credential_resolution_enabled'] is False and r['live_transports_enabled'] is False
