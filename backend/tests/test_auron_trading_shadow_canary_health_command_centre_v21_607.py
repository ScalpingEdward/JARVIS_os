from dataclasses import replace
from datetime import datetime,timedelta,timezone
from app.trading.auron_trading_shadow_canary_adapter_v21_605 import TradingShadowCanaryAdapter
from app.trading.auron_trading_shadow_canary_health_command_centre_v21_607 import TradingShadowCanaryHealthCommandCentre
from app.core.auron_integration_readiness_v21_607 import get_integration_readiness

def build(tmp_path,max_age=300):
    tmp_path.mkdir(parents=True,exist_ok=True)
    a=TradingShadowCanaryAdapter(tmp_path/'adapter.db'); return TradingShadowCanaryHealthCommandCentre(tmp_path/'cc.db',a,tmp_path/'exec.db',tmp_path/'rec.db',max_age_seconds=max_age),a

def test_fresh_healthy_evidence_certifies_and_snapshot_keeps_live_trading_off(tmp_path):
    cc,_=build(tmp_path); now=datetime.now(timezone.utc); cc.record_health(healthy=True,observed_at=now.isoformat()); h=cc.certify_latest_health(now=(now+timedelta(seconds=5)).isoformat()); s=cc.snapshot()
    assert h['certified'] is True and h['drift_detected'] is False
    assert s['broker_network_enabled'] is False and s['live_order_placement_enabled'] is False and s['position_mutation_enabled'] is False and s['production_transport_enabled'] is False and s['commands_execute_directly'] is False

def test_stale_unhealthy_and_missing_evidence_fail_closed(tmp_path):
    cc,_=build(tmp_path,60); now=datetime.now(timezone.utc); cc.record_health(healthy=False,observed_at=(now-timedelta(seconds=61)).isoformat()); h=cc.certify_latest_health(now=now.isoformat())
    assert {'provider-unhealthy','health-evidence-stale'} <= set(h['blockers'])
    empty,_=build(tmp_path/'empty'); assert 'health-evidence-missing' in empty.certify_latest_health()['blockers']

def test_descriptor_drift_is_detected(tmp_path):
    cc,a=build(tmp_path); cc.record_health(healthy=True); original=a.descriptor; a.descriptor=lambda: replace(original(),live_order_placement_enabled=True); h=cc.certify_latest_health()
    assert h['certified'] is False and h['drift_detected'] is True and 'adapter-config-drift' in h['blockers']

def test_operator_stop_persists_and_command_never_executes(tmp_path):
    cc,a=build(tmp_path); cc.record_health(healthy=True); stopped=cc.stop('activation-trading-1',actor='operator-1'); command=cc.record_command('place live order now',actor='operator-1')
    assert stopped['state']=='stopped' and a.is_stopped('activation-trading-1') is True and command['state']=='recorded-not-executed'
    assert cc.snapshot()['live_order_placement_enabled'] is False

def test_g20_readiness_advances_to_g21_without_live_execution():
    r=get_integration_readiness(); assert r['roadmap_version']=='v21.607' and r['next_item']=='G21-provider-expansion-promotion-decision'
    assert r['trading_execution_enabled'] is False and r['trading_broker_network_enabled'] is False and r['live_transports_enabled'] is False
