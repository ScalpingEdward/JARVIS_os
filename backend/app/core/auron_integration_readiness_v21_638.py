from __future__ import annotations

from app.core.auron_integration_readiness_v21_637 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.638",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H30-research-real-provider-transport-object-injection-gate",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-object-h29-design-certification-bound",
            "research-real-transport-object-exactly-one-object-injected",
            "research-real-transport-object-scope-identity-enforced",
            "research-real-transport-object-revocable",
            "research-real-transport-object-network-execution-still-disabled",
        ),
        "next_item": "H31-research-real-provider-transport-object-injection-certification",
        "core_next_gate": "research-real-provider-transport-object-injection-certification",
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
        "real_provider_transport_object_injection_design_certified": True,
        "real_provider_transport_object_present": True,
        "real_provider_transport_injected": True,
        "real_provider_transport_object_revocable": True,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
