from app.core.auron_integration_readiness_v21_561 import get_integration_readiness
from app.research.auron_research_adapter_onboarding_v21_556 import ResearchProviderDescriptor, ResearchProviderHealth
from app.research.auron_research_controlled_watch_v21_561 import ControlledResearchWatchService
from app.research.auron_research_evidence_policy_v21_559 import ResearchEvidenceProvenanceConfidencePolicy
from app.research.auron_research_read_search_fetch_v21_558 import ProviderFetchedDocument, ProviderSearchHit, ResearchReadSearchFetchIntegration
from app.research.auron_research_registry_evidence_v21_557 import ResearchRegistryEvidenceStore
from app.research.auron_research_report_simulation_v21_560 import ResearchReportSimulationService


class HealthyProvider:
    def descriptor(self):
        return ResearchProviderDescriptor(
            provider_id='research-test', display_name='Research Test',
            capabilities=('search','fetch','source-metadata','citations','snapshot'),
            supported_modes=('simulation','read-only'), supports_source_attribution=True,
            supports_stable_source_ids=True, supports_snapshotting=True,
        )

    def read_health(self):
        return ResearchProviderHealth(
            provider_id='research-test', reachable=True, authenticated=True,
            source_metadata_available=True, observed_at='2026-08-17T10:05:00+00:00',
            external_calls_made=0,
        )

    def search(self, query_text: str, *, limit: int):
        return (ProviderSearchHit('doc-1','https://example.com/gold','Gold','gold evidence',1),)[:limit]

    def fetch(self, provider_source_ref: str):
        return ProviderFetchedDocument(
            'doc-1','https://example.com/gold','Gold','full gold evidence','Example Research',
            'Example','2026-08-17T09:00:00+00:00','2026-08-17T10:05:00+00:00'
        )


class WrongProvider(HealthyProvider):
    def descriptor(self):
        d = super().descriptor()
        return ResearchProviderDescriptor(
            provider_id='wrong-provider', display_name=d.display_name,
            capabilities=d.capabilities, supported_modes=d.supported_modes,
            supports_source_attribution=d.supports_source_attribution,
            supports_stable_source_ids=d.supports_stable_source_ids,
            supports_snapshotting=d.supports_snapshotting,
        )


def stack(tmp_path):
    registry = ResearchRegistryEvidenceStore(tmp_path/'registry.sqlite3',fresh_for_seconds=3600,stale_after_seconds=7200)
    integration = ResearchReadSearchFetchIntegration(tmp_path/'sync.sqlite3',registry)
    policy = ResearchEvidenceProvenanceConfidencePolicy(registry)
    reports = ResearchReportSimulationService(tmp_path/'reports.sqlite3',registry,policy)
    watches = ControlledResearchWatchService(tmp_path/'watches.sqlite3',integration,reports)
    return watches


def test_watch_defaults_fail_closed(tmp_path):
    watches = stack(tmp_path)
    policy = watches.configure(provider_id='research-test',query_text='gold outlook',interval_seconds=300,now='2026-08-17T10:00:00+00:00')
    run = watches.run_if_due(policy.watch_id,HealthyProvider(),at='2026-08-17T10:05:00+00:00')
    assert run is not None
    assert run.state.startswith('blocked:')
    assert 'watch-disabled' in run.state
    assert 'operator-enablement-required' in run.state
    assert 'watch-kill-switch-active' in run.state
    assert run.external_calls_made == 0
    assert run.downstream_actions_made == 0


def test_enabled_watch_runs_governed_read_and_local_report_only(tmp_path):
    watches = stack(tmp_path)
    policy = watches.configure(
        provider_id='research-test',query_text='gold outlook',interval_seconds=300,
        enabled=True,operator_enabled=True,kill_switch=False,now='2026-08-17T10:00:00+00:00'
    )
    run = watches.run_if_due(policy.watch_id,HealthyProvider(),at='2026-08-17T10:05:00+00:00')
    assert run is not None
    assert run.state == 'completed-report-simulated'
    assert run.query_id
    assert run.report_id
    assert run.external_calls_made == 2
    assert run.downstream_actions_made == 0


def test_watch_not_due_does_nothing(tmp_path):
    watches = stack(tmp_path)
    policy = watches.configure(
        provider_id='research-test',query_text='gold outlook',interval_seconds=300,
        enabled=True,operator_enabled=True,kill_switch=False,now='2026-08-17T10:00:00+00:00'
    )
    assert watches.run_if_due(policy.watch_id,HealthyProvider(),at='2026-08-17T10:04:59+00:00') is None


def test_watch_run_is_idempotent_for_same_schedule_slot(tmp_path):
    watches = stack(tmp_path)
    policy = watches.configure(
        provider_id='research-test',query_text='gold outlook',interval_seconds=300,
        enabled=True,operator_enabled=True,kill_switch=False,now='2026-08-17T10:00:00+00:00'
    )
    first = watches.run_if_due(policy.watch_id,HealthyProvider(),at='2026-08-17T10:05:00+00:00')
    second = watches.run(policy.watch_id,HealthyProvider(),scheduled_for='2026-08-17T10:05:00+00:00',started_at='2026-08-17T10:05:01+00:00')
    assert first == second
    assert len(watches.list_runs(policy.watch_id)) == 1


def test_provider_identity_mismatch_blocks_without_external_calls(tmp_path):
    watches = stack(tmp_path)
    policy = watches.configure(
        provider_id='research-test',query_text='gold outlook',interval_seconds=300,
        enabled=True,operator_enabled=True,kill_switch=False,now='2026-08-17T10:00:00+00:00'
    )
    run = watches.run_if_due(policy.watch_id,WrongProvider(),at='2026-08-17T10:05:00+00:00')
    assert run is not None
    assert run.state == 'blocked:provider-identity-mismatch'
    assert run.external_calls_made == 0


def test_d14_readiness_advances_to_d15_with_global_defaults_off():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.561'
    assert readiness['next_item'] == 'D15-research-reconciliation-freshness-retry'
    assert readiness['research_watch_capability_available'] is True
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['research_downstream_execution_enabled'] is False
