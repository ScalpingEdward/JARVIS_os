from app.research.auron_research_evidence_policy_v21_559 import ResearchEvidenceProvenanceConfidencePolicy
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore
from app.research.auron_research_report_simulation_v21_560 import ResearchReportSimulationError, ResearchReportSimulationService
from app.core.auron_integration_readiness_v21_560 import get_integration_readiness


def stack(tmp_path):
    store = ResearchRegistryEvidenceStore(tmp_path/'research.sqlite3',fresh_for_seconds=3600,stale_after_seconds=7200)
    query = store.record_query('gold outlook','provider-a',requested_at='2026-08-17T10:00:00+00:00')
    source = store.upsert_source(provider_id='provider-a',url='https://example.com/a',title='Gold report',content='gold evidence',
                                 attribution='Example Research',publisher='Example',published_at='2026-08-17T09:00:00+00:00',retrieved_at='2026-08-17T10:00:00+00:00')
    store.record_result(query.query_id,source.source_id,rank=1,snippet='gold evidence',observed_at='2026-08-17T10:00:00+00:00')
    policy = ResearchEvidenceProvenanceConfidencePolicy(store)
    service = ResearchReportSimulationService(tmp_path/'reports.sqlite3',store,policy)
    return store, query, source, service


def test_report_is_deterministic_and_idempotent(tmp_path):
    _, query, _, service = stack(tmp_path)
    first = service.assemble(query.query_id,minimum_confidence='medium',now='2026-08-17T10:30:00+00:00')
    second = service.assemble(query.query_id,minimum_confidence='medium',now='2026-08-17T10:30:00+00:00')
    assert first.report_id == second.report_id
    assert first.report_hash == second.report_hash
    assert first == second
    assert first.external_calls_made == 0
    assert first.downstream_execution_enabled is False


def test_report_contains_explicit_citation_and_evidence_hash(tmp_path):
    _, query, _, service = stack(tmp_path)
    report = service.assemble(query.query_id,now='2026-08-17T10:30:00+00:00')
    assert report.evidence_count == 1
    assert '[R1]' in report.body_markdown
    assert 'https://example.com/a' in report.body_markdown
    assert report.citations[0].evidence_hash
    assert report.citations[0].confidence == 'high'


def test_changed_source_blocks_old_evidence_from_report(tmp_path):
    store, query, source, service = stack(tmp_path)
    store.upsert_source(provider_id='provider-a',url=source.canonical_url,title='Gold report',content='changed',
                        attribution='Example Research',publisher='Example',published_at='2026-08-17T09:00:00+00:00',retrieved_at='2026-08-17T10:10:00+00:00')
    try:
        service.assemble(query.query_id,now='2026-08-17T10:30:00+00:00')
        assert False, 'expected no admissible evidence'
    except ResearchReportSimulationError as exc:
        assert 'no admissible evidence' in str(exc)


def test_stale_evidence_cannot_enter_report(tmp_path):
    _, query, _, service = stack(tmp_path)
    try:
        service.assemble(query.query_id,now='2026-08-17T13:00:01+00:00')
        assert False, 'expected stale evidence rejection'
    except ResearchReportSimulationError as exc:
        assert 'no admissible evidence' in str(exc)


def test_report_persists_and_lists(tmp_path):
    _, query, _, service = stack(tmp_path)
    report = service.assemble(query.query_id,now='2026-08-17T10:30:00+00:00')
    assert service.get(report.report_id) == report
    assert service.list_reports(query.query_id) == (report,)


def test_d13_readiness_advances_to_controlled_watch_without_enabling_it():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.560'
    assert readiness['next_item'] == 'D14-controlled-research-watch-execution'
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
