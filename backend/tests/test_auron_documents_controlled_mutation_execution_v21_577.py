from app.documents.auron_documents_controlled_mutation_execution_v21_577 import ControlledDocumentsMutationExecutionService, DocumentsProviderMutationResult
from app.documents.auron_documents_mutation_simulation_v21_576 import DocumentMutationIntent, DocumentsMutationSimulationService
from app.documents.auron_documents_provenance_access_policy_v21_575 import DocumentsProvenanceVersionAccessPolicy
from app.documents.auron_documents_registry_state_v21_573 import DocumentsRegistryStateStore
from app.core.auron_integration_readiness_v21_577 import get_integration_readiness


class Writer:
    def execute_mutation(self, *, plan, idempotency_key):
        return DocumentsProviderMutationResult('provider-op-1',plan.item_id,None,'submitted',1)


def setup(tmp_path):
    store=DocumentsRegistryStateStore(tmp_path/'r.sqlite3')
    root=store.observe_item(provider_id='p',provider_item_ref='root',kind='folder',name='Root')
    f=store.observe_item(provider_id='p',provider_item_ref='f',kind='file',name='a.txt',parent_item_id=root.item_id)
    v=store.observe_version(item_id=f.item_id,provider_version_ref='v1',content_hash='a'*64,size_bytes=1)
    policy=DocumentsProvenanceVersionAccessPolicy(tmp_path/'p.sqlite3',store)
    for item in (root,f): policy.grant(actor_id='op',provider_id='p',item_id=item.item_id,allowed_purposes=('read','mutation-simulation'))
    sim=DocumentsMutationSimulationService(tmp_path/'s.sqlite3',store,policy)
    plan=sim.simulate(DocumentMutationIntent('update','p','op',item_id=f.item_id,expected_version_id=v.version_id,content_hash='b'*64))
    return store,policy,sim,plan


def test_default_transport_and_scope_fail_closed(tmp_path):
    store,policy,sim,plan=setup(tmp_path)
    service=ControlledDocumentsMutationExecutionService(tmp_path/'e.sqlite3',sim,store,policy)
    decision=service.execute(plan.plan_id)
    assert decision.state=='blocked'
    assert 'provider-execution-not-enabled' in decision.blockers
    assert decision.external_calls_made==0


def test_enabled_scope_still_uses_disabled_writer_by_default(tmp_path):
    store,policy,sim,plan=setup(tmp_path)
    service=ControlledDocumentsMutationExecutionService(tmp_path/'e.sqlite3',sim,store,policy)
    service.configure_scope('p',enabled=True,operator_enabled=True,kill_switch=False)
    decision=service.execute(plan.plan_id)
    assert decision.state=='execution-transport-disabled'
    assert decision.external_calls_made==0


def test_controlled_writer_submission_is_idempotent(tmp_path):
    store,policy,sim,plan=setup(tmp_path)
    service=ControlledDocumentsMutationExecutionService(tmp_path/'e.sqlite3',sim,store,policy,Writer())
    service.configure_scope('p',enabled=True,operator_enabled=True,kill_switch=False)
    first=service.execute(plan.plan_id); second=service.execute(plan.plan_id)
    assert first==second
    assert first.state=='provider-submitted'
    assert first.idempotency_key==first.execution_id
    assert first.external_calls_made==1


def test_current_version_drift_blocks_execution(tmp_path):
    store,policy,sim,plan=setup(tmp_path)
    item=store.get_item(plan.item_id)
    store.observe_version(item_id=item.item_id,provider_version_ref='v2',content_hash='c'*64,size_bytes=1)
    service=ControlledDocumentsMutationExecutionService(tmp_path/'e.sqlite3',sim,store,policy,Writer())
    service.configure_scope('p',enabled=True,operator_enabled=True,kill_switch=False)
    decision=service.execute(plan.plan_id)
    assert decision.state=='blocked'
    assert 'current-version-drift' in decision.blockers


def test_kill_switch_blocks_provider_call(tmp_path):
    store,policy,sim,plan=setup(tmp_path)
    service=ControlledDocumentsMutationExecutionService(tmp_path/'e.sqlite3',sim,store,policy,Writer())
    service.configure_scope('p',enabled=True,operator_enabled=True,kill_switch=True)
    decision=service.execute(plan.plan_id)
    assert decision.state=='blocked'
    assert 'provider-kill-switch-active' in decision.blockers
    assert decision.external_calls_made==0


def test_d30_readiness_advances_to_reconciliation():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.577'
    assert r['next_item']=='D31-documents-reconciliation-conflict-retry-delete-safeguards'
    assert r['documents_write_enabled'] is False
