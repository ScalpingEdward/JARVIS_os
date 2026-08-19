from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.documents.auron_documents_readonly_canary_adapter_v21_597 import DocumentsReadonlyCanaryAdapter
from app.documents.auron_documents_canary_health_command_centre_v21_599 import DocumentsCanaryHealthCommandCentre
from app.core.auron_integration_readiness_v21_599 import get_integration_readiness


def build(tmp_path,max_age=300):
    adapter=DocumentsReadonlyCanaryAdapter(tmp_path/'adapter.db')
    cc=DocumentsCanaryHealthCommandCentre(tmp_path/'cc.db',adapter,tmp_path/'exec.db',tmp_path/'rec.db',max_age_seconds=max_age)
    return cc,adapter


def test_fresh_healthy_evidence_certifies_and_snapshot_is_safe(tmp_path):
    cc,_=build(tmp_path); now=datetime.now(timezone.utc); cc.record_health(healthy=True,observed_at=now.isoformat())
    h=cc.certify_latest_health(now=(now+timedelta(seconds=5)).isoformat()); snap=cc.snapshot()
    assert h['certified'] is True and h['drift_detected'] is False
    assert snap['content_read_enabled'] is False and snap['mutation_enabled'] is False
    assert snap['delete_enabled'] is False and snap['move_enabled'] is False
    assert snap['network_transport_enabled'] is False and snap['production_transport_enabled'] is False
    assert snap['commands_execute_directly'] is False


def test_stale_and_unhealthy_evidence_fail_closed(tmp_path):
    cc,_=build(tmp_path,60); now=datetime.now(timezone.utc)
    cc.record_health(healthy=False,observed_at=(now-timedelta(seconds=61)).isoformat())
    h=cc.certify_latest_health(now=now.isoformat())
    assert h['certified'] is False
    assert {'provider-unhealthy','health-evidence-stale'} <= set(h['blockers'])


def test_descriptor_drift_is_detected(tmp_path):
    cc,adapter=build(tmp_path); cc.record_health(healthy=True)
    original=adapter.descriptor
    adapter.descriptor=lambda: replace(original(),allowed_actions=original().allowed_actions+('delete-file',))
    h=cc.certify_latest_health()
    assert h['certified'] is False and h['drift_detected'] is True and 'adapter-config-drift' in h['blockers']


def test_operator_stop_persists_and_commands_never_execute(tmp_path):
    cc,adapter=build(tmp_path); cc.record_health(healthy=True)
    stopped=cc.stop('activation-doc-1',actor='operator-1',reason='manual-stop')
    command=cc.record_command('delete file f-1',actor='operator-1')
    assert stopped['state']=='stopped' and adapter.is_stopped('activation-doc-1') is True
    assert command['state']=='recorded-not-executed'
    snap=cc.snapshot(); assert any(a['kind']=='stop' for a in snap['alerts'])
    assert snap['mutation_enabled'] is False and snap['delete_enabled'] is False


def test_missing_health_evidence_is_visible_as_alert(tmp_path):
    cc,_=build(tmp_path); snap=cc.snapshot()
    assert snap['health']['certified'] is False
    assert 'health-evidence-missing' in snap['health']['blockers']
    assert any(a['kind']=='health' for a in snap['alerts'])


def test_g12_readiness_advances_to_g13():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.599'
    assert r['next_item']=='G13-next-provider-vertical-selection'
    assert r['live_transports_enabled'] is False and r['trading_execution_enabled'] is False
