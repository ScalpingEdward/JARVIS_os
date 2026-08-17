from app.core.auron_integration_readiness_v21_558 import get_integration_readiness
from app.research.auron_research_adapter_onboarding_v21_556 import (
    ResearchProviderDescriptor,
    ResearchProviderHealth,
)
from app.research.auron_research_read_search_fetch_v21_558 import (
    ProviderFetchedDocument,
    ProviderSearchHit,
    ResearchReadIntegrationError,
    ResearchReadSearchFetchIntegration,
)
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore


class HealthyProvider:
    def descriptor(self):
        return ResearchProviderDescriptor(
            provider_id='research-test',
            display_name='Research Test',
            capabilities=('search','fetch','source-metadata','citations','snapshot'),
            supported_modes=('simulation','read-only'),
            supports_source_attribution=True,
            supports_stable_source_ids=True,
            supports_snapshotting=True,
        )

    def read_health(self):
        return ResearchProviderHealth(
            provider_id='research-test', reachable=True, authenticated=True,
            source_metadata_available=True, observed_at='2026-08-17T11:00:00+00:00',
            external_calls_made=0,
        )

    def search(self, query_text: str, *, limit: int):
        return (
            ProviderSearchHit('doc-1','https://example.com/a','A','first evidence',1),
            ProviderSearchHit('doc-2','https://example.com/b','B','second evidence',2),
        )[:limit]

    def fetch(self, provider_source_ref: str):
        docs = {
            'doc-1': ProviderFetchedDocument('doc-1','https://example.com/a','A','full A','Example A','Example','2026-08-17T09:00:00+00:00','2026-08-17T11:01:00+00:00'),
            'doc-2': ProviderFetchedDocument('doc-2','https://example.com/b','B','full B','Example B','Example','2026-08-17T09:30:00+00:00','2026-08-17T11:01:30+00:00'),
        }
        return docs[provider_source_ref]


class IdentityMismatchProvider(HealthyProvider):
    def fetch(self, provider_source_ref: str):
        return ProviderFetchedDocument('wrong-ref','https://example.com/a','A','full A','Example A','Example',None,'2026-08-17T11:01:00+00:00')


class UrlMismatchProvider(HealthyProvider):
    def fetch(self, provider_source_ref: str):
        return ProviderFetchedDocument(provider_source_ref,'https://example.com/wrong','A','full A','Example A','Example',None,'2026-08-17T11:01:00+00:00')


def test_certified_provider_populates_d10_registry(tmp_path):
    registry = ResearchRegistryEvidenceStore(tmp_path/'registry.sqlite3')
    integration = ResearchReadSearchFetchIntegration(tmp_path/'sync.sqlite3', registry)
    summary = integration.run_query(HealthyProvider(),'gold outlook',limit=2,requested_at='2026-08-17T11:00:00+00:00')
    assert summary.state == 'read-sync-complete'
    assert len(summary.sources) == 2
    assert len(summary.results) == 2
    assert len(integration.list_sync_records(summary.query.query_id)) == 2
    assert summary.external_calls_made == 3
    assert summary.downstream_actions_made == 0


def test_limit_bounds_provider_work(tmp_path):
    registry = ResearchRegistryEvidenceStore(tmp_path/'registry.sqlite3')
    integration = ResearchReadSearchFetchIntegration(tmp_path/'sync.sqlite3', registry)
    summary = integration.run_query(HealthyProvider(),'q',limit=1)
    assert len(summary.sources) == 1
    assert summary.external_calls_made == 2


def test_provider_source_identity_mismatch_fails_closed(tmp_path):
    registry = ResearchRegistryEvidenceStore(tmp_path/'registry.sqlite3')
    integration = ResearchReadSearchFetchIntegration(tmp_path/'sync.sqlite3', registry)
    try:
        integration.run_query(IdentityMismatchProvider(),'q',limit=1)
        assert False, 'expected identity mismatch'
    except ResearchReadIntegrationError as exc:
        assert 'identity mismatch' in str(exc)


def test_search_fetch_url_mismatch_fails_closed(tmp_path):
    registry = ResearchRegistryEvidenceStore(tmp_path/'registry.sqlite3')
    integration = ResearchReadSearchFetchIntegration(tmp_path/'sync.sqlite3', registry)
    try:
        integration.run_query(UrlMismatchProvider(),'q',limit=1)
        assert False, 'expected URL mismatch'
    except ResearchReadIntegrationError as exc:
        assert 'URL mismatch' in str(exc)


def test_d11_readiness_advances_without_downstream_execution():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.558'
    assert readiness['next_item'] == 'D12-research-evidence-provenance-confidence-policy'
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
