from app.research.auron_research_evidence_policy_v21_559 import ResearchEvidenceProvenanceConfidencePolicy
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore
from app.core.auron_integration_readiness_v21_559 import get_integration_readiness


def build(tmp_path, *, retrieved='2026-08-17T10:00:00+00:00', publisher='Example', published='2026-08-17T09:00:00+00:00'):
    store = ResearchRegistryEvidenceStore(tmp_path/'r.sqlite3', fresh_for_seconds=3600, stale_after_seconds=7200)
    query = store.record_query('gold outlook','provider-a',requested_at='2026-08-17T10:00:00+00:00')
    source = store.upsert_source(provider_id='provider-a',url='https://example.com/a',title='A',content='evidence',
                                 attribution='Example Research',publisher=publisher,published_at=published,retrieved_at=retrieved)
    result = store.record_result(query.query_id,source.source_id,rank=1,snippet='evidence',observed_at=retrieved)
    return store, query, source, result


def test_fresh_complete_evidence_is_high_confidence(tmp_path):
    store, query, _, result = build(tmp_path)
    assessment = ResearchEvidenceProvenanceConfidencePolicy(store).assess(query.query_id,result.result_id,now='2026-08-17T10:30:00+00:00')
    assert assessment.admissible is True
    assert assessment.confidence == 'high'
    assert assessment.score == 1.0


def test_source_change_invalidates_old_evidence_hash(tmp_path):
    store, query, source, result = build(tmp_path)
    store.upsert_source(provider_id='provider-a',url=source.canonical_url,title='A',content='changed',attribution='Example Research',
                        publisher='Example',published_at='2026-08-17T09:00:00+00:00',retrieved_at='2026-08-17T10:10:00+00:00')
    assessment = ResearchEvidenceProvenanceConfidencePolicy(store).assess(query.query_id,result.result_id,now='2026-08-17T10:20:00+00:00')
    assert assessment.admissible is False
    assert assessment.confidence == 'rejected'
    assert 'evidence-integrity-mismatch' in assessment.blockers


def test_stale_evidence_is_rejected(tmp_path):
    store, query, _, result = build(tmp_path)
    assessment = ResearchEvidenceProvenanceConfidencePolicy(store).assess(query.query_id,result.result_id,now='2026-08-17T13:00:01+00:00')
    assert assessment.admissible is False
    assert 'source-evidence-stale' in assessment.blockers


def test_missing_metadata_reduces_confidence_without_faking_truth(tmp_path):
    store, query, _, result = build(tmp_path,publisher=None,published=None)
    assessment = ResearchEvidenceProvenanceConfidencePolicy(store).assess(query.query_id,result.result_id,now='2026-08-17T10:30:00+00:00')
    assert assessment.admissible is True
    assert assessment.confidence == 'high'
    assert assessment.score == 0.8


def test_minimum_confidence_filters_admissible_evidence(tmp_path):
    store, query, _, _ = build(tmp_path,publisher=None,published=None)
    policy = ResearchEvidenceProvenanceConfidencePolicy(store)
    assert len(policy.admissible_evidence(query.query_id,minimum_confidence='high',now='2026-08-17T10:30:00+00:00')) == 1


def test_d12_readiness_advances_to_report_simulation():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.559'
    assert readiness['next_item'] == 'D13-research-simulation-report-assembly'
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
