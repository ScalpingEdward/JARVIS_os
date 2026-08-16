from app.communications.auron_communications_adapter_onboarding_v21_548 import (
    CommunicationsAdapterOnboardingPolicy,
    CommunicationsProviderDescriptor,
    CommunicationsProviderHealth,
    DisabledCommunicationsProviderBoundary,
)


class HealthyReadOnlyProvider:
    def descriptor(self):
        return CommunicationsProviderDescriptor(
            provider_id='communications-test',
            display_name='Communications Test',
            capabilities=('identity', 'health', 'read', 'draft', 'send'),
            supported_modes=('simulation', 'read-only', 'live'),
            requires_operator_approval=True,
            supports_idempotency=True,
            supports_reconciliation=True,
        )

    def read_health(self):
        return CommunicationsProviderHealth(
            provider_id='communications-test',
            reachable=True,
            authenticated=True,
            identity_verified=True,
            permissions_verified=True,
            observed_at='2026-08-16T00:00:00+00:00',
            external_calls_made=1,
        )


class UnsafeProvider(HealthyReadOnlyProvider):
    def descriptor(self):
        return CommunicationsProviderDescriptor(
            provider_id='unsafe',
            display_name='Unsafe',
            capabilities=('identity', 'health', 'send'),
            supported_modes=('live',),
            requires_operator_approval=False,
        )


def test_healthy_provider_is_certified_read_only_but_never_outbound_enabled():
    decision = CommunicationsAdapterOnboardingPolicy().evaluate(HealthyReadOnlyProvider())
    assert decision.accepted is True
    assert decision.allowed_mode == 'read-only'
    assert decision.outbound_execution_enabled is False
    assert decision.external_calls_made == 1


def test_disabled_boundary_fails_closed_without_external_calls():
    decision = CommunicationsAdapterOnboardingPolicy().evaluate(DisabledCommunicationsProviderBoundary())
    assert decision.accepted is False
    assert 'required-capabilities-missing' in decision.blockers
    assert 'provider-health-unavailable' in decision.blockers
    assert decision.outbound_execution_enabled is False
    assert decision.external_calls_made == 0


def test_provider_without_simulation_and_operator_approval_is_rejected():
    decision = CommunicationsAdapterOnboardingPolicy().evaluate(UnsafeProvider())
    assert decision.accepted is False
    assert 'required-capabilities-missing' in decision.blockers
    assert 'simulation-mode-required' in decision.blockers
    assert 'operator-approval-must-be-required' in decision.blockers
    assert decision.outbound_execution_enabled is False


def test_d1_certification_cannot_enable_outbound_execution():
    policy = CommunicationsAdapterOnboardingPolicy()
    decision = policy.require_onboarded(policy.evaluate(HealthyReadOnlyProvider()))
    assert decision.accepted is True
    assert decision.outbound_execution_enabled is False
