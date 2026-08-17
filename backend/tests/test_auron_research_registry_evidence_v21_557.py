from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore, ResearchRegistryError
from app.core.auron_integration_readiness_v21_557 import get_integration_readiness


def test_query_source_result_are_persistent_and_normalized(tmp_path):
    store = ResearchRegistryEvidenceStore(tmp_path/'research.sqlite3')
    query = store.record_query('gold outlook', 'provider-a', requested_at='2026-08-17T10:00:00+00:00')
    source = store.upsert_source(provider_id='provider-a', url='HTTPS://Example.COM/report#section', title='Gold report',
                                 content='Evidence body', attribution='Example Research', retrieved_at='2026-08-17T10:01:00+00:00')
    result = store.record_result(query.query_id, source.source_id, rank=1, snippet='Evidence body')
    assert source.canonical_url == 'https://example.com/report'
    assert store.get_query(query.query_id) == query
    assert store.get_source(source.source_id) == source
    assert store.list_results(query.query_id) == (result,)


def test_source_identity_is_stable_and_content_change_is_historicized(tmp_path):
    store = ResearchRegistryEvidenceStore(tmp_path/'research.sqlite3')
    first = store.upsert_source(provider_id='p', url='https://example.com/a', title='A', content='v1', attribution='Example')
    second = store.upsert_source(provider_id='p', url='https://example.com/a', title='A2', content='v2', attribution='Example')
    assert first.source_id == second.source_id
    assert first.content_hash != second.content_hash
    history = store.source_history(first.source_id)
    assert len(history) == 2
    assert history[0]['content_hash'] == first.content_hash
    assert history[1]['content_hash'] == second.content_hash


def test_evidence_hash_is_bound_to_source_content(tmp_path):
    store = ResearchRegistryEvidenceStore(tmp_path/'research.sqlite3')
    query = store.record_query('q','p')
    source = store.upsert_source(provider_id='p',url='https://example.com/a',title='A',content='v1',attribution='Example')
    first = store.record_result(query.query_id,source.source_id,rank=1,snippet='same')
    store.upsert_source(provider_id='p',url='https://example.com/a',title='A',content='v2',attribution='Example')
    second = store.record_result(query.query_id,source.source_id,rank=1,snippet='same')
    assert first.evidence_hash != second.evidence_hash


def test_freshness_state_is_explicit(tmp_path):
    store = ResearchRegistryEvidenceStore(tmp_path/'research.sqlite3',fresh_for_seconds=60,stale_after_seconds=120)
    source = store.upsert_source(provider_id='p',url='https://example.com/a',title='A',content='v',attribution='Example',retrieved_at='2026-08-17T10:00:00+00:00')
    assert store.evidence_state(source.source_id,now='2026-08-17T10:00:30+00:00').freshness_state == 'fresh'
    assert store.evidence_state(source.source_id,now='2026-08-17T10:01:30+00:00').freshness_state == 'aging'
    assert store.evidence_state(source.source_id,now='2026-08-17T10:03:00+00:00').freshness_state == 'stale'


def test_cross_provider_result_fails_closed(tmp_path):
    store = ResearchRegistryEvidenceStore(tmp_path/'research.sqlite3')
    query = store.record_query('q','provider-a')
    source = store.upsert_source(provider_id='provider-b',url='https://example.com/a',title='A',content='v',attribution='Example')
    try:
        store.record_result(query.query_id,source.source_id,rank=1,snippet='x')
        assert False, 'expected provider mismatch'
    except ResearchRegistryError as exc:
        assert 'provider mismatch' in str(exc)


def test_d10_readiness_advances_to_d11_without_actions():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.557'
    assert readiness['next_item'] == 'D11-research-read-health-integration'
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
