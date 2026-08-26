from __future__ import annotations

from app.core.auron_integration_readiness_v21_623 import (
    get_integration_readiness as previous_readiness,
)


def get_integration_readiness() -> dict:
    p = previous_readiness()
    return {
        **p,
        "roadmap_version": "v21.624",
        "current_phase": "H-controlled-external-provider-sandbox-integration",
        "current_item": "H16-research-real-provider-canary-execution-boundary-design",
        "completed_gates": tuple(p["completed_gates"])
        + (
            "research-real-canary-boundary-h15-token-bound",
            "research-real-canary-boundary-exactly-once-token-consumption-designed",
            "research-real-canary-boundary-endpoint-capability-pinned",
            "research-real-canary-boundary-request-budget-fail-closed-designed",
            "research-real-canary-boundary-audit-semantics-designed",
            "research-real-canary-boundary-transport-implementation-absent",
        ),
        "next_item": "H17-research-real-provider-canary-execution-boundary-certification",
        "core_next_gate": "research-real-provider-canary-execution-boundary-certification",
        "live_transports_enabled": False,
        "external_provider_network_enabled": False,
        "external_provider_write_enabled": False,
        "external_provider_credential_resolution_enabled": False,
        "real_provider_transport_configured": False,
        "real_provider_activation_enabled": False,
        "real_provider_canary_token_enabled": True,
        "real_provider_canary_execution_boundary_designed": True,
        "real_provider_canary_execution_enabled": False,
        "trading_execution_enabled": False,
    }
