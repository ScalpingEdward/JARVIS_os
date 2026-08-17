from app.research.auron_research_command_centre_v21_563 import ResearchCommandCentre
from app.research.auron_research_controlled_watch_v21_561 import ControlledResearchWatchService
from app.research.auron_research_evidence_policy_v21_559 import ResearchEvidenceProvenanceConfidencePolicy
from app.research.auron_research_read_search_fetch_v21_558 import ResearchReadSearchFetchIntegration
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore
from app.research.auron_research_report_simulation_v21_560 import ResearchReportSimulationService
from app.research.auron_research_watch_reconciliation_v21_562 import ResearchWatchReconciliationService
from app.core.auron_integration_readiness_v21_563 import get_integration_readiness


def stack(tmp_path):
    registry = ResearchRegistryEvidenceStore(tmp_path/'registry.sqlite3',fresh_for_seconds=3600,stale_after_seconds=7200)
    query = registry.record_query('gold outlook','provider-a',requested_at='2026-08-17T10:00:00+00:00')
    source = registry.upsert_source(provider_id='provider-a',url='https://example.com/a',title='Gold report',content='gold evidence',
                                    attribution='Example Research',publisher='Example',published_at='2026-08-17T09:00:00+00:00',retrieved_at='2026-08-17T10:00:00+00:00')
    registry.record_result(query.query_id,source.source_id,rank=1,snippet='gold evidence',observed_at='2026-08-17T10:00:00+00:00')
    policy = ResearchEvidenceProvenanceConfidencePolicy(registry)
    reports = ResearchReportSimulationService(tmp_path/'reports.sqlite3',registry,policy)
    reports.assemble(query.query_id,now='2026-08-17T10:30:00+00:00')
    integration = ResearchReadSearchFetchIntegration(tmp_path/'sync.sqlite3',registry)
    watches = ControlledResearchWatchService(tmp_path/'watches.sqlite3',integration,reports)
    watch = watches.configure(provider_id='provider-a',query_text='gold outlook',interval_seconds=300,
                              result_limit=5,minimum_confidence='medium',enabled=True,
                              operator_enabled=True,kill_switch=False,now='2026-08-17T10:00:00+00:00')
    reconciliation = ResearchWatchReconciliationService(tmp_path/'reconciliation.sqlite3',watches)
    centre = ResearchCommandCentre(tmp_path/'command-centre.sqlite3',registry,reports,watches,reconciliation)
    return centre, watches, watch


def test_snapshot_exposes_research_operational_state(tmp_path):
    centre, _, _ = stack(tmp_path)
    snapshot = centre.snapshot(now='2026-08-17T10:30:00+00:00')
    assert snapshot['workspace'] == 'research'
    assert snapshot['command_field_enabled'] is True
    assert len(snapshot['queries']) == 1
    assert len(snapshot['sources']) == 1
    assert len(snapshot['results']) == 1
    assert len(snapshot['reports']) == 1
    assert len(snapshot['watch_policies']) == 1
    assert snapshot['source_freshness'][0]['freshness_state'] == 'fresh'
    assert snapshot['unattended_actions_enabled_by_default'] is False
    assert snapshot['downstream_execution_enabled'] is False


def test_snapshot_surfaces_stale_evidence_alert(tmp_path):
    centre, _, _ = stack(tmp_path)
    snapshot = centre.snapshot(now='2026-08-17T13:00:01+00:00')
    assert any(alert['kind'] == 'freshness' and alert['state'] == 'stale' for alert in snapshot['alerts'])


def test_watch_kill_switch_control_preserves_other_policy_fields(tmp_path):
    centre, watches, watch = stack(tmp_path)
    updated = centre.set_watch_kill_switch(watch.watch_id,active=True,now='2026-08-17T10:31:00+00:00')
    assert updated['enabled'] is True
    assert updated['operator_enabled'] is True
    assert updated['kill_switch'] is True
    stored = watches.get_policy(watch.watch_id)
    assert stored.query_text == 'gold outlook'
    assert stored.interval_seconds == 300


def test_command_field_is_persistent_but_never_executes(tmp_path):
    centre, _, _ = stack(tmp_path)
    entry = centre.record_command('watch gold news every hour',actor='operator')
    assert entry.state == 'recorded-not-executed'
    assert centre.list_commands()[0].command_text == 'watch gold news every hour'


def test_d16_marks_research_architecture_complete_without_unattended_default():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.563'
    assert readiness['research_vertical_architecture_complete'] is True
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
    assert readiness['next_item'] == 'D17-next-vertical-selection'
