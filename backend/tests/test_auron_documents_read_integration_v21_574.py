import hashlib
import pytest

from app.documents.auron_documents_adapter_onboarding_v21_572 import DocumentsProviderDescriptor, DocumentsProviderHealth
from app.documents.auron_documents_read_integration_v21_574 import DocumentsReadIntegration, DocumentsReadIntegrationError, ProviderItemObservation, ProviderContentFetch
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore
from app.core.auron_integration_readiness_v21_574 import get_integration_readiness


CONTENT = b'hello jarvis'
HASH = hashlib.sha256(CONTENT).hexdigest()


class Provider:
    def descriptor(self):
        return DocumentsProviderDescriptor('files','Files',('identity','health','metadata','read','inspect'),('read-only',),True,True,True,True)
    def read_health(self):
        return DocumentsProviderHealth('files',True,True,True,True,True,'2026-08-18T09:00:00+00:00',1)
    def list_items(self,parent_ref=None):
        return (
            ProviderItemObservation('files','root','folder','Root'),
            ProviderItemObservation('files','a','file','a.txt','root','text/plain',provider_version_ref='v1',content_hash=HASH,size_bytes=len(CONTENT)),
        )
    def search_items(self,query):
        return (ProviderItemObservation('files','a','file','a.txt',mime_type='text/plain',provider_version_ref='v1',content_hash=HASH,size_bytes=len(CONTENT)),)
    def fetch_content(self,provider_item_ref,provider_version_ref):
        return ProviderContentFetch('files',provider_item_ref,provider_version_ref,CONTENT,HASH)


def test_list_sync_populates_registry_with_parent_and_version(tmp_path):
    store=DocumentsRegistryStateStore(tmp_path/'d.sqlite3'); service=DocumentsReadIntegration(store)
    result=service.list_and_sync(Provider())
    item=store.get_item_by_provider_ref('files','a')
    assert len(result['items']) == 2 and item.parent_item_id is not None
    assert item.current_version_id is not None and result['external_calls_made'] == 2
    assert result['write_enabled'] is False


def test_search_sync_is_read_only(tmp_path):
    store=DocumentsRegistryStateStore(tmp_path/'d.sqlite3'); service=DocumentsReadIntegration(store)
    result=service.search_and_sync(Provider(),'a')
    assert len(result['items']) == 1 and result['delete_enabled'] is False


def test_fetch_requires_registered_exact_version_and_verifies_content(tmp_path):
    store=DocumentsRegistryStateStore(tmp_path/'d.sqlite3'); service=DocumentsReadIntegration(store)
    service.list_and_sync(Provider())
    result=service.fetch_verified(Provider(),provider_item_ref='a',provider_version_ref='v1')
    assert result['content'] == CONTENT and result['verified_content_hash'] == HASH
    with pytest.raises(DocumentsReadIntegrationError):
        service.fetch_verified(Provider(),provider_item_ref='a',provider_version_ref='v2')


def test_provider_identity_drift_fails_closed(tmp_path):
    class Bad(Provider):
        def search_items(self,query):
            return (ProviderItemObservation('other','x','file','x.txt'),)
    with pytest.raises(DocumentsReadIntegrationError):
        DocumentsReadIntegration(DocumentsRegistryStateStore(tmp_path/'d.sqlite3')).search_and_sync(Bad(),'x')


def test_content_drift_fails_closed(tmp_path):
    class Bad(Provider):
        def fetch_content(self,*args):
            return ProviderContentFetch('files','a','v1',b'changed')
    store=DocumentsRegistryStateStore(tmp_path/'d.sqlite3'); service=DocumentsReadIntegration(store)
    service.list_and_sync(Provider())
    with pytest.raises(DocumentsReadIntegrationError):
        service.fetch_verified(Bad(),provider_item_ref='a',provider_version_ref='v1')


def test_d27_readiness_advances_to_policy():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.574'
    assert r['next_item']=='D28-documents-provenance-version-access-policy'
    assert r['documents_write_enabled'] is False
