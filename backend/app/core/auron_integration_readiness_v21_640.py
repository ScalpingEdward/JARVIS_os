from __future__ import annotations

from app.core.auron_integration_readiness_v21_639 import get_integration_readiness as previous_readiness


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.640",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H32-research-real-provider-network-execution-authorization-design",
        "completed_gates": tuple(p["completed_gates"]) + (
            "research-real-network-execution-h31-injection-certified",
            "research-real-network-execution-short-lived-authorization-designed",
            "research-real-network-execution-one-shot-consumption-designed",
            "research-real-network-execution-reapproval-kill-rollback-designed",
            "research-real-network-execution-still-disabled",
        ),
        "next_item": "H33-research-real-provider-network-execution-authorization-design-certification",
        "core_next_gate": "research-real-provider-network-execution-authorization-design-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_object_injection_certified": True,
        "real_provider_network_execution_authorization_designed": True,
        "real_provider_network_execution_authorization_issued": False,
        "real_provider_network_execution_authorization_consumed": False,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
