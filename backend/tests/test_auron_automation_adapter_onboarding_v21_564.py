from app.automation.auron_automation_adapter_onboarding_v21_564 import (
    AutomationAdapterOnboardingPolicy,
    AutomationProviderDescriptor,
    AutomationProviderHealth,
    DisabledAutomationProviderBoundary,
)
from app.core.auron_integration_readiness_v21_564 import get_integration_readiness


class HealthyProvider:
    def descriptor(self):
        return AutomationProviderDescriptor(
            provider_id='automation-test',
            display_name='Automation Test',
            capabilities=(
                'identity','health','catalog','inspect','simulate','schedule',
                'execute','cancel','result-read','idempotency',
            ),
            supported_modes=('simulation','read-only','controlled-live'),
            requires_operator_approval=True,
            supports_idempotency=True,
            supports_cancellation=True,
            supports_result_reconciliation=True,
            supports_scoped_credentials=True,
        )

    def read_health(self):
        return AutomationProviderHealth(
            provider_id='automation-test',
            reachable=True,
            authenticated=True,
            identity_verified=True,
            catalog_available=True,
            permissions_scoped=True,
            observed_at='2026-08-17T13:00:00+00:00',
            external_calls_made=1,
        )


class UnsafeProvider(HealthyProvider):
    def descriptor(self):
        return AutomationProviderDescriptor(
            provider_id='unsafe',
            display_name='Unsafe',
            capabilities=('identity','health','execute'),
            supported_modes=('controlled-live',),
            requires_operator_approval=False,
            supports_idempotency=False,
            supports_result_reconciliation=False,
            supports_scoped_credentials=False,
        )


def test_healthy_provider_is_certified_but_execution_stays_disabled():
    decision = AutomationAdapterOnboardingPolicy().evaluate(HealthyProvider())
    assert decision.accepted is True
    assert decision.allowed_mode == 'read-only'
    assert decision.execution_enabled is False
    assert decision.external_calls_made == 1


def test_disabled_provider_fails_closed_without_execution():
    decision = AutomationAdapterOnboardingPolicy().evaluate(DisabledAutomationProviderBoundary())
    assert decision.accepted is False
    assert 'required-capabilities-missing' in decision.blockers
    assert 'provider-health-unavailable' in decision.blockers
    assert decision.execution_enabled is False
    assert decision.external_calls_made == 0


def test_unsafe_provider_is_rejected_for_missing_governance_properties():
    decision = AutomationAdapterOnboardingPolicy().evaluate(UnsafeProvider())
    assert decision.accepted is False
    assert 'required-capabilities-missing' in decision.blockers
    assert 'simulation-mode-required' in decision.blockers
    assert 'operator-approval-must-be-required' in decision.blockers
    assert 'idempotency-support-required' in decision.blockers
    assert 'result-reconciliation-required' in decision.blockers
    assert 'scoped-credentials-required' in decision.blockers
    assert decision.execution_enabled is False


def test_d17_readiness_selects_automation_without_execution():
    readiness = get_integration_readiness()
    assert readiness['roadmap_version'] == 'v21.564'
    assert readiness['current_item'] == 'D17-automation-provider-adapter-onboarding'
    assert readiness['next_item'] == 'D18-automation-workflow-trigger-action-registry'
    assert readiness['automation_execution_enabled'] is False
    assert readiness['automation_cross_vertical_execution_enabled'] is False
    assert readiness['external_calls_made'] == 0
