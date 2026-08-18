import pytest
from app.core.auron_cross_vertical_simulation_harness_v21_581 import CrossVerticalSimulationHarness, CrossVerticalSimulationError
from app.core.auron_integration_readiness_v21_581 import get_integration_readiness


def test_deterministic_cross_vertical_simulation(tmp_path):
    h=CrossVerticalSimulationHarness(tmp_path/'x.db')
    handoffs=(
        {'source_vertical':'research','target_vertical':'automation','boundary':'research.report.accepted','payload':{'report_id':'r1'}},
        {'source_vertical':'automation','target_vertical':'instagram-content','boundary':'content.draft.simulation','payload':{'draft':'d1'}},
    )
    a=h.simulate('scenario-1',handoffs,at='2026-08-18T16:00:00+00:00')
    b=h.simulate('scenario-1',handoffs,at='2026-08-18T17:00:00+00:00')
    assert a.run_id==b.run_id and a.run_hash==b.run_hash
    assert a.provider_writes_made==0 and a.live_actions_made==0
    assert all(s.state=='simulated-not-executed' for s in a.steps)


def test_provider_bypass_boundary_is_rejected(tmp_path):
    h=CrossVerticalSimulationHarness(tmp_path/'x.db')
    with pytest.raises(CrossVerticalSimulationError):
        h.simulate('s',({'source_vertical':'automation','target_vertical':'trading','boundary':'provider:mt5','payload':{}},))


def test_unknown_or_same_vertical_is_rejected(tmp_path):
    h=CrossVerticalSimulationHarness(tmp_path/'x.db')
    with pytest.raises(CrossVerticalSimulationError):
        h.simulate('s1',({'source_vertical':'unknown','target_vertical':'trading','boundary':'x','payload':{}},))
    with pytest.raises(CrossVerticalSimulationError):
        h.simulate('s2',({'source_vertical':'research','target_vertical':'research','boundary':'x','payload':{}},))


def test_e2_readiness_advances_to_e3():
    r=get_integration_readiness()
    assert r['roadmap_version']=='v21.581'
    assert r['next_item']=='E3-cross-vertical-reconciliation-observability-certification'
    assert r['live_transports_enabled'] is False
    assert r['cross_vertical_direct_provider_bypass_allowed'] is False
