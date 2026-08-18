import sqlite3

from app.core.auron_cross_vertical_reconciliation_observability_v21_582 import (
    CrossVerticalReconciliationObservabilityCertification,
)
from app.core.auron_cross_vertical_simulation_harness_v21_581 import CrossVerticalSimulationHarness
from app.core.auron_integration_readiness_v21_582 import get_integration_readiness


def harness(tmp_path):
    sim = CrossVerticalSimulationHarness(tmp_path/'sim.sqlite3')
    sim.simulate('scenario-1', (
        {'source_vertical':'research','target_vertical':'automation','boundary':'research-report','payload':{'id':'r1'}},
        {'source_vertical':'automation','target_vertical':'instagram-content','boundary':'content-draft','payload':{'id':'c1'}},
    ), at='2026-08-18T16:00:00+00:00')
    return sim


def test_reconciliation_certifies_traceability_and_replay_safety(tmp_path):
    sim = harness(tmp_path)
    cert = CrossVerticalReconciliationObservabilityCertification(tmp_path/'rec.sqlite3', sim)
    record = cert.reconcile_scenario('scenario-1', at='2026-08-18T16:01:00+00:00')
    assert record.state == 'certified-observable-replay-safe'
    assert record.blockers == ()
    assert len(record.observed_steps) == 2
    assert all(step.correlation_id.startswith('xcorr-') for step in record.observed_steps)
    assert all(step.failure_visible and step.replay_safe for step in record.observed_steps)
    assert record.provider_writes_made == 0 and record.live_actions_made == 0


def test_reconciliation_is_idempotent_by_run(tmp_path):
    sim = harness(tmp_path)
    cert = CrossVerticalReconciliationObservabilityCertification(tmp_path/'rec.sqlite3', sim)
    first = cert.reconcile_scenario('scenario-1', at='2026-08-18T16:01:00+00:00')
    second = cert.reconcile_scenario('scenario-1', at='2026-08-18T17:01:00+00:00')
    assert first == second


def test_step_state_drift_fails_certification(tmp_path):
    sim = harness(tmp_path)
    run = sim.get_by_scenario('scenario-1')
    with sqlite3.connect(sim.db_path) as conn:
        conn.execute("UPDATE cross_vertical_simulation_steps SET state='failed-visible' WHERE run_id=? AND ordinal=2", (run.run_id,))
    cert = CrossVerticalReconciliationObservabilityCertification(tmp_path/'rec.sqlite3', sim)
    record = cert.reconcile_scenario('scenario-1')
    assert record.state == 'certification-failed'
    assert 'unexpected-step-state:2' in record.blockers


def test_live_or_provider_side_effects_fail_certification(tmp_path):
    sim = harness(tmp_path)
    run = sim.get_by_scenario('scenario-1')
    with sqlite3.connect(sim.db_path) as conn:
        conn.execute('UPDATE cross_vertical_simulation_runs SET provider_writes_made=1,live_actions_made=1 WHERE run_id=?',(run.run_id,))
    record = CrossVerticalReconciliationObservabilityCertification(tmp_path/'rec.sqlite3', sim).reconcile_scenario('scenario-1')
    assert 'provider-writes-detected' in record.blockers
    assert 'live-actions-detected' in record.blockers


def test_e3_readiness_advances_to_e4():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.582'
    assert readiness['next_item'] == 'E4-production-readiness-canary-gate'
    assert readiness['live_transports_enabled'] is False
