from __future__ import annotations

from app.core.auron_integration_readiness_v21_629 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.630",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H22-research-real-provider-transport-injection-activation-design-certification",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-activation-design-exact-binding-certified",
            "research-real-transport-activation-opaque-reference-certified",
            "research-real-transport-activation-readonly-reapproval-kill-rollback-certified",
            "research-real-transport-activation-zero-authorization-zero-transport-certified",
        ),
        "next_item": "H23-research-real-provider-transport-injection-authorization-gate",
        "core_next_gate": "research-real-provider-transport-injection-authorization-gate",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_transport_injection_activation_designed": True,
        "real_provider_transport_injection_activation_certified": True,
        "real_provider_transport_injection_authorized": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
