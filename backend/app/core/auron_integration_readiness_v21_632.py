from __future__ import annotations

from app.core.auron_integration_readiness_v21_631 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.632",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H24-research-real-provider-transport-injection-boundary-design",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-transport-injection-h23-authorization-boundary-designed",
            "research-real-transport-injection-exactly-once-authorization-consumption-designed",
            "research-real-transport-injection-identity-lifecycle-revocation-designed",
            "research-real-transport-injection-budget-audit-boundary-designed",
            "research-real-transport-injection-network-execution-still-disabled",
        ),
        "next_item": "H25-research-real-provider-transport-injection-boundary-certification",
        "core_next_gate": "research-real-provider-transport-injection-boundary-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_transport_injection_authorization_gate_enabled": True,
        "real_provider_transport_injection_authorized": True,
        "real_provider_transport_injection_boundary_designed": True,
        "real_provider_transport_injection_authorization_consumed": False,
        "real_provider_transport_injected": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
