from __future__ import annotations

from app.core.auron_integration_readiness_v21_625 import (
    get_integration_readiness as previous_readiness,
)


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.626",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H18-research-real-provider-one-shot-canary-execution-gate",
        "completed_gates": tuple(p["completed_gates"])
        + (
            "research-real-canary-h17-certified-token-consumption-gated",
            "research-real-canary-token-exactly-once-consumption-enforced",
            "research-real-canary-bounded-session-opened-without-transport",
            "research-real-canary-session-budget-inherited",
            "research-real-canary-transport-still-disabled",
        ),
        "next_item": "H19-research-real-provider-transport-injection-contract",
        "core_next_gate": "research-real-provider-transport-injection-contract",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_canary_token_enabled": True,
        "real_provider_canary_execution_boundary_designed": True,
        "real_provider_canary_execution_boundary_certified": True,
        "real_provider_canary_session_gate_enabled": True,
        "real_provider_canary_transport_enabled": False,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
