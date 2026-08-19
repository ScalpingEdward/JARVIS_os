import pytest

from app.core.auron_external_provider_contract_registry_v21_609 import (
    ExternalProviderContractError, ExternalProviderContractRegistry,
)
from app.core.auron_integration_readiness_v21_609 import get_integration_readiness


def registry(tmp_path):
    return ExternalProviderContractRegistry(tmp_path/'provider-contracts.db')


def test_research_readonly_sandbox_contract_is_persistent_and_idempotent(tmp_path):
    r=registry(tmp_path)
    kwargs=dict(vertical='research',provider_id='research-external-readonly-sandbox',
        adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',
        allowed_capabilities=('search-readonly','inspect-source-metadata'),
        credential_ref='secretref://research/sandbox/read-only')
    a=r.register(**kwargs); b=r.register(**kwargs)
    assert a.contract_id==b.contract_id
    assert a.read_only is True and a.provider_write_enabled is False
    assert a.network_transport_enabled is False and a.production_transport_enabled is False
    assert r.require_secretless_sandbox(a.contract_id).provider_id=='research-external-readonly-sandbox'


def test_public_descriptor_never_exposes_credential_reference(tmp_path):
    r=registry(tmp_path); c=r.register(vertical='research',provider_id='research-external-readonly-sandbox',
        adapter_id='research-external-readonly-sandbox-v1',environment='sandbox',
        allowed_capabilities=('search-readonly',),credential_ref='secretref://research/sandbox')
    public=r.export_public_descriptor(c.contract_id)
    assert 'credential_ref' not in public and public['credential_ref_present'] is True


def test_raw_secret_fields_are_rejected(tmp_path):
    r=registry(tmp_path)
    with pytest.raises(ExternalProviderContractError):
        r.register(vertical='research',provider_id='p',adapter_id='a',environment='sandbox',
            allowed_capabilities=('search-readonly',),metadata={'api_key':'raw-value'})


def test_write_network_production_and_non_sandbox_contracts_fail_closed(tmp_path):
    r=registry(tmp_path)
    base=dict(vertical='research',provider_id='p',adapter_id='a',allowed_capabilities=('search-readonly',))
    for extra in (
        {'environment':'production'},
        {'environment':'sandbox','read_only':False},
        {'environment':'sandbox','provider_write_enabled':True},
        {'environment':'sandbox','network_transport_enabled':True},
        {'environment':'sandbox','production_transport_enabled':True},
    ):
        with pytest.raises(ExternalProviderContractError):
            r.register(**base,**extra)


def test_h1_readiness_advances_to_h2_without_enabling_transport():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.609'
    assert r['current_phase']=='H-controlled-external-provider-sandbox-integration'
    assert r['next_item']=='H2-research-external-readonly-sandbox-adapter'
    assert r['external_provider_network_enabled'] is False
    assert r['external_provider_write_enabled'] is False
    assert r['live_transports_enabled'] is False and r['trading_execution_enabled'] is False
