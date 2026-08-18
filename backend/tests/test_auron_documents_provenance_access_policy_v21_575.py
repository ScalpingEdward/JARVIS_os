import pytest

from app.documents.auron_documents_provenance_access_policy_v21_575 import (
    DocumentsPolicyError,
    DocumentsProvenanceVersionAccessPolicy,
)
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore
from app.core.auron_integration_readiness_v21_575 import get_integration_readiness


def setup_store(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path/'docs.sqlite3')
    item = store.observe_item(provider_id='files',provider_item_ref='a',kind='file',name='a.txt')
    version = store.observe_version(item_id=item.item_id,provider_version_ref='v1',content_hash='abc')
    item = store.get_item(item.item_id)
    return store,item,version


def test_explicit_access_grant_allows_read(tmp_path):
    store,item,version = setup_store(tmp_path)
    policy = DocumentsProvenanceVersionAccessPolicy(tmp_path/'policy.sqlite3',store)
    policy.grant(actor_id='op',provider_id='files',item_id=item.item_id,allowed_purposes=('read',))
    decision = policy.evaluate(item_id=item.item_id,actor_id='op',purpose='read')
    assert decision.allowed is True
    assert decision.provenance_verified is True
    assert decision.access_verified is True
    assert decision.external_calls_made == 0


def test_mutation_simulation_requires_exact_current_version(tmp_path):
    store,item,version = setup_store(tmp_path)
    policy = DocumentsProvenanceVersionAccessPolicy(tmp_path/'policy.sqlite3',store)
    policy.grant(actor_id='op',provider_id='files',item_id=item.item_id,
                 allowed_purposes=('mutation-simulation',))
    bad = policy.evaluate(item_id=item.item_id,actor_id='op',purpose='mutation-simulation',version_id='wrong')
    assert bad.allowed is False
    assert 'exact-current-version-required' in bad.blockers
    good = policy.require_mutation_simulation_authorized(item_id=item.item_id,version_id=version.version_id,actor_id='op')
    assert good.allowed is True
    assert good.current_version_required is True


def test_provider_wide_grant_is_supported_but_explicit(tmp_path):
    store,item,_ = setup_store(tmp_path)
    policy = DocumentsProvenanceVersionAccessPolicy(tmp_path/'policy.sqlite3',store)
    policy.grant(actor_id='op',provider_id='files',allowed_purposes=('read',))
    assert policy.evaluate(item_id=item.item_id,actor_id='op').allowed is True


def test_revocation_blocks_access(tmp_path):
    store,item,_ = setup_store(tmp_path)
    policy = DocumentsProvenanceVersionAccessPolicy(tmp_path/'policy.sqlite3',store)
    grant = policy.grant(actor_id='op',provider_id='files',item_id=item.item_id,allowed_purposes=('read',))
    policy.revoke(grant.grant_id)
    decision = policy.evaluate(item_id=item.item_id,actor_id='op')
    assert decision.allowed is False
    assert 'explicit-access-grant-required' in decision.blockers


def test_mutation_execution_remains_fail_closed(tmp_path):
    store,item,version = setup_store(tmp_path)
    policy = DocumentsProvenanceVersionAccessPolicy(tmp_path/'policy.sqlite3',store)
    with pytest.raises(DocumentsPolicyError):
        policy.grant(actor_id='op',provider_id='files',item_id=item.item_id,
                     allowed_purposes=('mutation-execution',))
    decision = policy.evaluate(item_id=item.item_id,actor_id='op',purpose='mutation-execution',version_id=version.version_id)
    assert decision.allowed is False
    assert 'D28-mutation-execution-not-authorized' in decision.blockers


def test_unregistered_item_fails_provenance(tmp_path):
    store = DocumentsRegistryStateStore(tmp_path/'docs.sqlite3')
    policy = DocumentsProvenanceVersionAccessPolicy(tmp_path/'policy.sqlite3',store)
    decision = policy.evaluate(item_id='missing',actor_id='op')
    assert decision.allowed is False
    assert 'registered-provenance-required' in decision.blockers


def test_d28_readiness_advances_to_mutation_simulation():
    r = get_integration_readiness()
    assert r['roadmap_version'] == 'v21.575'
    assert r['next_item'] == 'D29-documents-deterministic-mutation-simulation'
    assert r['documents_write_enabled'] is False
    assert r['documents_delete_enabled'] is False
