from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.auron_capability_adapter_contract_v21_525 import (
    ContractOnlyAdapter,
    ExecutionContext,
    validate_adapter_contract,
)
from app.core.auron_command_centre_v21_528 import CommandCentreService, CommandCentreStore
from app.core.auron_execution_ledger_v21_526 import ExecutionAuditLedger
from app.core.auron_integration_readiness_v21_528 import get_integration_readiness
from app.core.auron_policy_gate_v21_527 import CentralPolicyGate, PolicyState


class CutoverCertificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CutoverCertification:
    certification_id: str
    state: str
    completed_gates: tuple[str, ...]
    verified_capabilities: tuple[str, ...]
    command_input_available: bool
    persistent_ledger_verified: bool
    policy_fail_closed_verified: bool
    simulation_path_verified: bool
    live_provider_execution_enabled: bool
    external_calls_made: int
    blockers: tuple[str, ...]


class CoreCutoverHarness:
    """End-to-end integration harness for the shared AURON core.

    This certifies the reusable core path only. It deliberately does not certify
    any broker, MT5, Meta, Telegram, or other provider for live execution.
    """

    REQUIRED_A_GATES = (
        'canonical-roadmap',
        'integration-readiness-registry',
        'capability-contract',
        'persistent-ledger',
        'idempotency',
        'reconciliation-primitives',
        'central-policy-gate',
        'operator-approval-gate',
        'environment-mode-gate',
        'global-kill-switch',
        'capability-kill-switches',
        'capability-scopes',
        'command-centre-integration',
        'command-input-preserved',
        'approval-workflow-visible',
        'audit-timeline-visible',
        'backend-state-visible',
    )

    def __init__(self, state_dir: str | Path) -> None:
        root = Path(state_dir)
        root.mkdir(parents=True, exist_ok=True)
        self.ledger_path = root / 'cutover_execution_ledger.sqlite3'
        self.command_path = root / 'cutover_command_centre.sqlite3'

    def certify(self) -> CutoverCertification:
        readiness = get_integration_readiness()
        blockers: list[str] = []
        completed = tuple(readiness.get('completed_gates', ()))

        for gate in self.REQUIRED_A_GATES:
            if gate not in completed:
                blockers.append(f'missing-gate:{gate}')

        policy = CentralPolicyGate()
        policy_snapshot = policy.snapshot()['policy']
        policy_fail_closed = (
            policy_snapshot['environment'] == 'development'
            and policy_snapshot['global_kill_switch'] is True
            and not policy_snapshot['live_capabilities']
        )
        if not policy_fail_closed:
            blockers.append('default-policy-not-fail-closed')

        ledger = ExecutionAuditLedger(self.ledger_path)
        store = CommandCentreStore(self.command_path)
        centre = CommandCentreService(store, ledger, policy)
        command_snapshot = centre.snapshot()
        command_input_available = command_snapshot.get('command_input_available') is True
        if not command_input_available:
            blockers.append('command-input-unavailable')
        if command_snapshot.get('command_execution_enabled') is not False:
            blockers.append('command-execution-must-remain-disabled-during-core-cutover')

        verified_capabilities: list[str] = []
        external_calls = 0
        for capability in ('core', 'trading', 'instagram-content-manager'):
            adapter = ContractOnlyAdapter(capability)
            contract = validate_adapter_contract(adapter)
            if not contract.get('contract_valid'):
                blockers.append(f'contract-invalid:{capability}')
                continue

            context = ExecutionContext(
                mode='simulation',
                request_id=f'cutover-{capability}-{uuid4()}',
                capability=capability,
            )
            sim_policy = CentralPolicyGate(
                PolicyState(enabled_scopes={capability: ('simulate',)})
            )
            decision = sim_policy.require(context, required_scope='simulate')
            if decision.external_execution_allowed:
                blockers.append(f'simulation-external-execution-allowed:{capability}')
                continue

            payload: dict[str, Any] = {'cutover_probe': True, 'capability': capability}
            intent = ledger.record_intent(context, payload)
            result = adapter.execute(context, payload)
            record = ledger.record_result(result)
            external_calls += result.external_calls_made

            if intent.request_id != record.request_id or record.status != 'simulated':
                blockers.append(f'ledger-flow-invalid:{capability}')
                continue
            if record.reconciliation_state != 'not-applicable':
                blockers.append(f'simulation-reconciliation-invalid:{capability}')
                continue
            verified_capabilities.append(capability)

        reopened = ExecutionAuditLedger(self.ledger_path)
        persistent_ledger_verified = all(
            reopened.list_recent(capability=capability, limit=1)
            for capability in verified_capabilities
        ) and len(verified_capabilities) == 3
        if not persistent_ledger_verified:
            blockers.append('persistent-ledger-reopen-verification-failed')

        if external_calls != 0:
            blockers.append('external-calls-detected-during-cutover')

        simulation_path_verified = len(verified_capabilities) == 3 and external_calls == 0
        state = 'core-cutover-certified' if not blockers else 'core-cutover-blocked'
        return CutoverCertification(
            certification_id=str(uuid4()),
            state=state,
            completed_gates=self.REQUIRED_A_GATES,
            verified_capabilities=tuple(verified_capabilities),
            command_input_available=command_input_available,
            persistent_ledger_verified=persistent_ledger_verified,
            policy_fail_closed_verified=policy_fail_closed,
            simulation_path_verified=simulation_path_verified,
            live_provider_execution_enabled=False,
            external_calls_made=external_calls,
            blockers=tuple(blockers),
        )


def certification_dict(certification: CutoverCertification) -> dict[str, Any]:
    return asdict(certification)


def require_core_cutover_certified(certification: CutoverCertification) -> None:
    if certification.state != 'core-cutover-certified' or certification.blockers:
        raise CutoverCertificationError('AURON core cutover certification failed: ' + ', '.join(certification.blockers))
    if certification.external_calls_made != 0:
        raise CutoverCertificationError('Core cutover certification must not make external calls')
    if certification.live_provider_execution_enabled:
        raise CutoverCertificationError('Core cutover must not enable any live provider execution')
