from app.core.auron_integration_readiness_v21_556 import get_integration_readiness
from app.research.auron_research_adapter_onboarding_v21_556 import (
    DisabledResearchProviderBoundary,
    ResearchAdapterOnboardingPolicy,
    ResearchProviderDescriptor,
    ResearchProviderHealth,
)


class HealthyResearchProvider:
    def descriptor(self):
        return ResearchProviderDescriptor(
            provider_id='research-test',
            display_name='Research Test',
            capabilities=('search', 'fetch', 'source-metadata', 'citations', 'snapshot'),
            supported_modes=('simulation', 'read-only'),
            supports_source_attribution=True,
            supports_stable_source_ids=True,
            supports_snapshotting=True,
        )

    def read_health(self):
        return ResearchProviderHealth(
            provider_id='research-test',
            reachable=True,
            authenticated=True,
            source_metadata_available=True,
            observed_at='2026-08-17T10:00:00+00:00',
            external_calls_made=1,
        )


class UnsafeResearchProvider(HealthyResearchProvider):
    def descriptor(self):
        return ResearchProviderDescriptor(
            provider_id='unsafe-research',
            display_name='Unsafe Research',
            capabilities=('search', 'fetch'),
            supported_modes=('read-only',),
            supports_source_attribution=False,
            supports_stable_source_ids=False,
            supports_snapshotting=False,
        )


def test_healthy_research_provider_is_read_only_certified_without_unattended_actions():
    decision = ResearchAdapterOnboardingPolicy().evaluate(HealthyResearchProvider())
    assert decision.accepted is True
    assert decision.allowed_mode == 'read-only'
    assert decision.unattended_action_enabled is False
    assert decision.external_calls_made == 1


def test_disabled_research_boundary_fails_closed():
    decision = ResearchAdapterOnboardingPolicy().evaluate(DisabledResearchProviderBoundary())
    assert decision.accepted is False
    assert 'required-capabilities-missing' in decision.blockers
    assert 'source-attribution-required' in decision.blockers
    assert 'stable-source-ids-required' in decision.blockers
    assert 'provider-health-unavailable' in decision.blockers
    assert decision.external_calls_made == 0


def test_unsafe_provider_without_simulation_and_provenance_is_rejected():
    decision = ResearchAdapterOnboardingPolicy().evaluate(UnsafeResearchProvider())
    assert decision.accepted is False
    assert 'required-capabilities-missing' in decision.blockers
    assert 'simulation-mode-required' in decision.blockers
    assert 'source-attribution-required' in decision.blockers
    assert 'stable-source-ids-required' in decision.blockers


def test_d9_readiness_advances_to_research_state_model():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.556'
    assert readiness['current_item'] == 'D9-research-provider-adapter-onboarding'
    assert readiness['next_item'] == 'D10-research-source-registry-state-model'
    assert readiness['research_provider_connected'] is False
    assert readiness['research_unattended_actions_enabled'] is False
    assert readiness['external_calls_made'] == 0
