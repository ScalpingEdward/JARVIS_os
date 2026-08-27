from __future__ import annotations

from app.core.auron_integration_readiness_v21_633 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.634",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H26-research-real-provider-transport-binding-gate",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-binding-h25-certification-consumed",
            "research-real-transport-binding-authorization-exactly-once-consumed",
            "research-real-transport-identity-bound-revocable",
            "research-real-transport-binding-zero-concrete-transport-zero-network",
        ),
        "next_item": "H27-research-real-provider-transport-binding-certification",
        "core_next_gate": "research-real-provider-transport-binding-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_transport_injection_authorization_gate_enabled": True,
        "real_provider_transport_injection_authorized": True,
        "real_provider_transport_injection_boundary_designed": True,
        "real_provider_transport_injection_boundary_certified": True,
        "real_provider_transport_injection_authorization_consumed": True,
        "real_provider_transport_identity_bound": True,
        "real_provider_transport_binding_revocable": True,
        "real_provider_transport_injected": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
