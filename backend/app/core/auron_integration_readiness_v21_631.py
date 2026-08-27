from __future__ import annotations

from app.core.auron_integration_readiness_v21_630 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.631",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H23-research-real-provider-transport-injection-authorization-gate",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-injection-h22-certification-bound",
            "research-real-transport-injection-short-lived-operator-authorization-issued",
            "research-real-transport-injection-reapproval-kill-rollback-gated",
            "research-real-transport-injection-authorization-no-injection-no-network",
        ),
        "next_item": "H24-research-real-provider-transport-injection-boundary-design",
        "core_next_gate": "research-real-provider-transport-injection-boundary-design",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_transport_injection_activation_designed": True,
        "real_provider_transport_injection_activation_certified": True,
        "real_provider_transport_injection_authorization_gate_enabled": True,
        "real_provider_transport_injection_authorized": True,
        "real_provider_transport_injected": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
