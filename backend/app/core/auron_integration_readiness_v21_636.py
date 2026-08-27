from __future__ import annotations

from app.core.auron_integration_readiness_v21_635 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.636",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H28-research-real-provider-transport-object-injection-design",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-object-injection-h27-binding-certified",
            "research-real-transport-object-contract-designed",
            "research-real-transport-object-exact-identity-binding-designed",
            "research-real-transport-object-revocation-lifecycle-designed",
            "research-real-transport-object-zero-object-zero-network-designed",
        ),
        "next_item": "H29-research-real-provider-transport-object-injection-design-certification",
        "core_next_gate": "research-real-provider-transport-object-injection-design-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_transport_identity_bound": True,
        "real_provider_transport_binding_revocable": True,
        "real_provider_transport_binding_certified": True,
        "real_provider_transport_object_injection_designed": True,
        "real_provider_transport_object_present": False,
        "real_provider_transport_injected": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
