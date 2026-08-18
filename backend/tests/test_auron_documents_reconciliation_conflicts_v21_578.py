import pytest
from types import SimpleNamespace

from app.documents.auron_documents_reconciliation_conflicts_v21_578 import DocumentsMutationReconciliationService, DocumentsObservedMutationResult, DocumentsReconciliationError
from app.core.auron_integration_readiness_v21_578 import get_integration_readiness


class Execution:
    def __init__(self,state='provider-submitted',ref='ref1'): self.state=state; self.ref=ref
    def get_by_plan(self,plan_id):
        return SimpleNamespace(execution_id='e1',plan_id=plan_id,provider_id='p',state=self.state,provider_ref=self.ref)
class Simulation:
    def __init__(self,kind='update'): self.kind=kind
    def get_plan(self,plan_id):
        return SimpleNamespace(kind=self.kind,content_hash='abc',destination_parent_item_id='dst')
class Registry:
    def get_item(self,item_id): return SimpleNamespace(provider_item_ref='dst-ref')
class Reader:
    def __init__(self,result): self.result=result
    def read_result(self,**kwargs): return self.result


def service(tmp_path,result=None,kind='update'):
    reader=Reader(result) if result else None
    return DocumentsMutationReconciliationService(tmp_path/'r.sqlite3',Execution(),Simulation(kind),Registry(),reader)


def test_successful_update_reconciles(tmp_path):
    r=DocumentsObservedMutationResult('ref1','p','item','v2','completed','abc')
    rec=service(tmp_path,r).reconcile('plan1')
    assert rec.state=='reconciled' and rec.conflict_detected is False and rec.delete_authorized is False


def test_update_content_conflict_is_fail_closed_and_not_retryable(tmp_path):
    r=DocumentsObservedMutationResult('ref1','p','item','v2','completed','different')
    rec=service(tmp_path,r).reconcile('plan1')
    assert rec.state=='conflict' and rec.conflict_detected is True and rec.retry_eligible is False


def test_move_parent_conflict_is_detected(tmp_path):
    r=DocumentsObservedMutationResult('ref1','p','item',None,'completed',parent_provider_item_ref='wrong')
    rec=service(tmp_path,r,'move').reconcile('plan1')
    assert rec.state=='conflict' and 'parent-conflict' in rec.blockers


def test_disabled_reader_is_bounded_retry_only(tmp_path):
    s=service(tmp_path)
    first=s.reconcile('plan1'); second=s.reconcile('plan1'); third=s.reconcile('plan1')
    assert first.retry_eligible is True and second.retry_eligible is True
    assert third.retry_eligible is False and third.state=='retry-exhausted'
    with pytest.raises(DocumentsReconciliationError): s.retry_authorization('e1')


def test_delete_is_never_authorized(tmp_path):
    s=service(tmp_path)
    assert s.authorize_delete('anything') is False


def test_d31_readiness_advances_to_command_centre():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.578'
    assert r['next_item']=='D32-documents-command-centre-operations'
    assert r['documents_delete_enabled'] is False
