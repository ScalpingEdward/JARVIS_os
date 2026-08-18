import hashlib
import pytest

from app.documents.auron_documents_mutation_simulation_v21_576 import DocumentMutationIntent, DocumentsMutationSimulationError, DocumentsMutationSimulationService
from app.documents.auron_documents_provenance_access_policy_v21_575 import DocumentsProvenanceVersionAccessPolicy
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore
from app.core.auron_integration_readiness_v21_576 import get_integration_readiness


def setup(tmp_path):
    store=DocumentsRegistryStateStore(tmp_path/'r.sqlite3')
    root=store.observe_item(provider_id='p',provider_item_ref='root',kind='folder',name='Root')
    dst=store.observe_item(provider_id='p',provider_item_ref='dst',kind='folder',name='Dst')
    file=store.observe_item(provider_id='p',provider_item_ref='f',kind='file',name='a.txt',parent_item_id=root.item_id)
    ver=store.observe_version(item_id=file.item_id,provider_version_ref='v1',content_hash='a'*64,size_bytes=1)
    policy=DocumentsProvenanceVersionAccessPolicy(tmp_path/'p.sqlite3',store)
    for item in (root,dst,file): policy.grant(actor_id='op',provider_id='p',item_id=item.item_id,allowed_purposes=('read','mutation-simulation'))
    return store,policy,root,dst,store.get_item(file.item_id),ver


def test_create_plan_is_deterministic_and_zero_write(tmp_path):
    store,policy,root,_,_,_=setup(tmp_path); service=DocumentsMutationSimulationService(tmp_path/'s.sqlite3',store,policy)
    intent=DocumentMutationIntent('create','p','op',parent_item_id=root.item_id,name='new.txt',content_hash=hashlib.sha256(b'x').hexdigest())
    a=service.simulate(intent,at='2026-08-18T10:00:00+00:00'); b=service.simulate(intent,at='2026-08-18T11:00:00+00:00')
    assert a.plan_id==b.plan_id and a.plan_hash==b.plan_hash
    assert a.state=='simulated-not-executed' and a.provider_writes_made==0


def test_update_requires_exact_current_version(tmp_path):
    store,policy,_,_,file,ver=setup(tmp_path); service=DocumentsMutationSimulationService(tmp_path/'s.sqlite3',store,policy)
    ok=service.simulate(DocumentMutationIntent('update','p','op',item_id=file.item_id,expected_version_id=ver.version_id,content_hash='b'*64))
    assert ok.expected_version_id==ver.version_id
    with pytest.raises(Exception):
        service.simulate(DocumentMutationIntent('update','p','op',item_id=file.item_id,expected_version_id='wrong',content_hash='b'*64))


def test_move_requires_authorized_same_provider_destination(tmp_path):
    store,policy,_,dst,file,ver=setup(tmp_path); service=DocumentsMutationSimulationService(tmp_path/'s.sqlite3',store,policy)
    plan=service.simulate(DocumentMutationIntent('move','p','op',item_id=file.item_id,expected_version_id=ver.version_id,destination_parent_item_id=dst.item_id))
    assert plan.destination_parent_item_id==dst.item_id and plan.provider_writes_made==0


def test_create_rejects_existing_item_identity(tmp_path):
    store,policy,root,_,file,_=setup(tmp_path); service=DocumentsMutationSimulationService(tmp_path/'s.sqlite3',store,policy)
    with pytest.raises(DocumentsMutationSimulationError):
        service.simulate(DocumentMutationIntent('create','p','op',item_id=file.item_id,parent_item_id=root.item_id,name='x'))


def test_d29_readiness_advances_to_controlled_boundary():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.576'
    assert r['next_item']=='D30-documents-controlled-create-update-move-boundary'
    assert r['documents_write_enabled'] is False
