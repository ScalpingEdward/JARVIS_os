from types import SimpleNamespace
import sqlite3
from app.documents.auron_documents_command_centre_v21_579 import DocumentsCommandCentre
from app.core.auron_integration_readiness_v21_579 import get_integration_readiness


class Obj:
    def __init__(self,path): self.db_path=str(path)
class Execution(Obj):
    def get_scope(self,p): return SimpleNamespace(provider_id=p,enabled=True,operator_enabled=True,kill_switch=True,updated_at='x')
    def configure_scope(self,p,**kw): return SimpleNamespace(provider_id=p,updated_at='y',**kw)
class Recon(Obj):
    def retry_authorization(self,e): return SimpleNamespace(execution_id=e,state='retry-eligible',retry_eligible=True)


def mkdb(path,sql):
    with sqlite3.connect(path) as c: c.executescript(sql)

def build(tmp_path):
    r=Obj(tmp_path/'registry.db'); p=Obj(tmp_path/'policy.db'); s=Obj(tmp_path/'sim.db'); e=Execution(tmp_path/'exec.db'); x=Recon(tmp_path/'rec.db')
    mkdb(r.db_path,"CREATE TABLE document_items(item_id TEXT,observed_at TEXT); CREATE TABLE document_versions(version_id TEXT,observed_at TEXT);")
    mkdb(p.db_path,"CREATE TABLE document_access_grants(grant_id TEXT,granted_at TEXT);")
    mkdb(s.db_path,"CREATE TABLE document_mutation_plans(plan_id TEXT,created_at TEXT);")
    mkdb(e.db_path,"CREATE TABLE document_mutation_execution_scopes(provider_id TEXT,enabled INT,operator_enabled INT,kill_switch INT,updated_at TEXT); INSERT INTO document_mutation_execution_scopes VALUES('p',1,1,1,'x'); CREATE TABLE document_mutation_executions(execution_id TEXT,state TEXT,created_at TEXT); INSERT INTO document_mutation_executions VALUES('e','blocked','x');")
    mkdb(x.db_path,"CREATE TABLE document_mutation_reconciliation(execution_id TEXT,state TEXT,reconciled_at TEXT); INSERT INTO document_mutation_reconciliation VALUES('e','conflict','x');")
    return DocumentsCommandCentre(tmp_path/'cc.db',r,p,s,e,x)


def test_snapshot_exposes_governed_workspace_and_alerts(tmp_path):
    snap=build(tmp_path).snapshot()
    assert snap['workspace']=='files-documents' and snap['command_field_enabled'] is True
    assert snap['delete_enabled'] is False and snap['recorded_commands_execute_directly'] is False
    assert len(snap['alerts'])==3

def test_kill_switch_and_retry_controls_support_dataclass_shaped_results(tmp_path):
    cc=build(tmp_path)
    assert cc.set_execution_kill_switch('p',active=False)['kill_switch'] is False
    assert cc.retry_status('e')['retry_eligible'] is True

def test_command_field_records_intent_without_execution(tmp_path):
    entry=build(tmp_path).record_command('show conflicts',actor='op')
    assert entry.state=='recorded-not-executed'

def test_delete_stays_denied(tmp_path): assert build(tmp_path).delete_authorized('x') is False

def test_d32_completes_documents_architecture():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.579'
    assert r['next_item']=='E1-cross-vertical-integration-certification'
    assert r['documents_write_enabled'] is False and r['documents_delete_enabled'] is False
