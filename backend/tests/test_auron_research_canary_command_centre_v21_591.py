from datetime import datetime, timezone

from app.core.auron_integration_readiness_v21_591 import get_integration_readiness
from app.research.auron_research_canary_command_centre_v21_591 import ResearchCanaryCommandCentre
from app.research.auron_research_provider_health_drift_v21_590 import ResearchProviderHealthDriftCertification
from app.research.auron_research_readonly_canary_adapter_v21_588 import ResearchReadonlyCanaryAdapter


def build(tmp_path):
    adapter=ResearchReadonlyCanaryAdapter(tmp_path/'adapter.db')
    health=ResearchProviderHealthDriftCertification(tmp_path/'health.db')
    health.record(adapter.descriptor(),healthy=True,observed_at=datetime.now(timezone.utc).isoformat())
    return ResearchCanaryCommandCentre(tmp_path/'cc.db',adapter,health,tmp_path/'exec.db',tmp_path/'rec.db'),adapter


def test_snapshot_exposes_descriptor_and_keeps_transports_disabled(tmp_path):
    cc,_=build(tmp_path); snap=cc.snapshot()
    assert snap['workspace']=='research-provider-canary'
    assert snap['descriptor']['provider_id']=='research-local-readonly'
    assert snap['network_transport_enabled'] is False
    assert snap['production_transport_enabled'] is False
    assert snap['commands_execute_directly'] is False


def test_health_certification_control_uses_latest_evidence(tmp_path):
    cc,_=build(tmp_path); result=cc.certify_latest_health()
    assert result['certified'] is True and result['drift_detected'] is False


def test_operator_stop_is_persistent_and_visible(tmp_path):
    cc,adapter=build(tmp_path)
    result=cc.stop('activation-1',actor='operator-1',reason='manual-check')
    assert result['state']=='stopped' and adapter.is_stopped('activation-1') is True
    snap=cc.snapshot(); assert len(snap['stops'])==1 and any(a['kind']=='stop' for a in snap['alerts'])


def test_command_is_recorded_not_executed(tmp_path):
    cc,_=build(tmp_path); entry=cc.record_command('show latest canary status',actor='operator-1')
    assert entry.state=='recorded-not-executed'


def test_g4_readiness_advances_to_g5():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.591'
    assert r['next_item']=='G5-next-provider-vertical-selection'
    assert r['live_transports_enabled'] is False
