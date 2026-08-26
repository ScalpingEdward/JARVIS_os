from __future__ import annotations

from app.core.auron_integration_readiness_v21_624 import (
    get_integration_readiness as previous_readiness,
)


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.625",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H17-research-real-provider-canary-execution-boundary-certification",
        "completed_gates": tuple(p["completed_gates"])
        + (
            "research-real-canary-boundary-h15-token-binding-certified",
            "research-real-canary-boundary-exactly-once-consumption-certified",
            "research-real-canary-boundary-endpoint-capability-budget-certified",
            "research-real-canary-boundary-audit-safety-certified",
            "research-real-canary-boundary-zero-transport-certified",
        ),
        "next_item": "H18-research-real-provider-one-shot-canary-execution-gate",
        "core_next_gate": "research-real-provider-one-shot-canary-execution-gate",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_canary_token_enabled": True,
        "real_provider_canary_execution_boundary_designed": True,
        "real_provider_canary_execution_boundary_certified": True,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
