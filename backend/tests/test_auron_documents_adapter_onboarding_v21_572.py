import pytest

from app.documents.auron_documents_adapter_onboarding_v21_572 import (
    DocumentsAdapterOnboardingPolicy,
    DocumentsOnboardingError,
    DocumentsProviderDescriptor,
    DocumentsProviderHealth,
)
from app.core.auron_integration_readiness_v21_572 import get_integration_readiness


class Provider:
    def descriptor(self):
        return DocumentsProviderDescriptor(
            provider_id='files', display_name='Files',
            capabilities=('identity','health','metadata','read','inspect'),
            permission_scopes=('read-only',), supports_read=True,
            supports_metadata=True, supports_content_fetch=True,
            supports_version_identity=True, supports_write=True, supports_delete=True,
        )

    def read_health(self):
        return DocumentsProviderHealth(
            provider_id='files', reachable=True, authenticated=True,
            identity_verified=True, read_scope_verified=True,
            metadata_available=True, observed_at='2026-08-18T10:00:00+00:00',
            external_calls_made=1,
        )


def test_read_provider_is_certified_but_mutations_remain_disabled():
    decision = DocumentsAdapterOnboardingPolicy().evaluate(Provider())
    assert decision.accepted is True
    assert decision.read_only_certified is True
    assert decision.write_enabled is False
    assert decision.delete_enabled is False
    assert decision.external_calls_made == 1


def test_identity_mismatch_fails_closed():
    class Bad(Provider):
        def read_health(self):
            health = super().read_health()
            return DocumentsProviderHealth('other', health.reachable, health.authenticated,
                health.identity_verified, health.read_scope_verified, health.metadata_available,
                health.observed_at, health.external_calls_made)
    decision = DocumentsAdapterOnboardingPolicy().evaluate(Bad())
    assert decision.accepted is False
    assert 'provider-identity-mismatch' in decision.blockers


def test_missing_version_identity_fails_closed():
    class Bad(Provider):
        def descriptor(self):
            d = super().descriptor()
            return DocumentsProviderDescriptor(d.provider_id,d.display_name,d.capabilities,d.permission_scopes,
                d.supports_read,d.supports_metadata,d.supports_content_fetch,False,d.supports_write,d.supports_delete)
    with pytest.raises(DocumentsOnboardingError):
        DocumentsAdapterOnboardingPolicy().require_onboarded(DocumentsAdapterOnboardingPolicy().evaluate(Bad()))


def test_d25_readiness_advances_to_registry_state():
    r = get_integration_readiness()
    assert r['roadmap_version'] == 'v21.572'
    assert r['current_item'] == 'D25-documents-provider-adapter-onboarding-contract'
    assert r['next_item'] == 'D26-documents-registry-normalized-state'
    assert r['documents_write_enabled'] is False
    assert r['documents_delete_enabled'] is False
