from __future__ import annotations

from app.core.auron_capability_adapter_contract_v21_525 import ContractOnlyAdapter, validate_adapter_contract
from app.core.auron_integration_readiness_v21_524 import get_integration_readiness as get_v21_524_readiness


def get_integration_readiness() -> dict:
    previous = get_v21_524_readiness()
    contracts = {
        capability: validate_adapter_contract(ContractOnlyAdapter(capability))
        for capability in ('core', 'trading', 'instagram-content-manager')
    }
    return {
        **previous,
        'roadmap_version': 'v21.525',
        'current_item': 'A2-unified-capability-adapter-contract',
        'completed_gates': ('canonical-roadmap', 'integration-readiness-registry', 'capability-contract'),
        'next_item': 'A3-persistent-execution-audit-ledger-idempotency-reconciliation',
        'core_next_gate': 'persistent-ledger',
        'contracts': contracts,
        'external_calls_made': 0,
    }
