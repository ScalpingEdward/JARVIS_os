from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

from app.core.auron_capability_adapter_contract_v21_525 import ExecutionContext

EnvironmentMode = Literal['development', 'staging', 'production']


class PolicyGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class PolicyState:
    environment: EnvironmentMode = 'development'
    global_kill_switch: bool = True
    capability_kill_switches: dict[str, bool] = field(default_factory=dict)
    enabled_scopes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    live_capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyDecision:
    request_id: str
    capability: str
    mode: str
    allowed: bool
    blockers: tuple[str, ...]
    required_scope: str
    environment: EnvironmentMode
    external_execution_allowed: bool
    external_calls_made: int = 0


class CentralPolicyGate:
    """Fail-closed policy boundary shared by every future provider adapter."""

    def __init__(self, state: PolicyState | None = None) -> None:
        self._state = state or PolicyState()

    @property
    def state(self) -> PolicyState:
        return self._state

    def replace_state(self, state: PolicyState) -> None:
        self._state = state

    def evaluate(self, context: ExecutionContext, *, required_scope: str) -> PolicyDecision:
        blockers: list[str] = []
        state = self._state

        if not required_scope.strip():
            raise PolicyGateError('required_scope must be explicit')

        scopes = state.enabled_scopes.get(context.capability, ())
        if required_scope not in scopes:
            blockers.append('capability-scope-missing')

        if context.mode == 'simulation':
            if 'simulate' not in scopes:
                blockers.append('simulation-scope-missing')
            allowed = not blockers
            return PolicyDecision(
                request_id=context.request_id,
                capability=context.capability,
                mode=context.mode,
                allowed=allowed,
                blockers=tuple(dict.fromkeys(blockers)),
                required_scope=required_scope,
                environment=state.environment,
                external_execution_allowed=False,
                external_calls_made=0,
            )

        if context.mode != 'live':
            blockers.append('unknown-execution-mode')
        if state.environment != 'production':
            blockers.append('environment-not-production')
        if state.global_kill_switch:
            blockers.append('global-kill-switch-active')
        if state.capability_kill_switches.get(context.capability, True):
            blockers.append('capability-kill-switch-active')
        if context.capability not in state.live_capabilities:
            blockers.append('capability-not-live-enabled')
        if not context.operator_approved:
            blockers.append('operator-approval-missing')
        if not context.external_execution_allowed:
            blockers.append('execution-context-policy-allowance-missing')
        if 'external.execute' not in scopes:
            blockers.append('external-execute-scope-missing')

        allowed = not blockers
        return PolicyDecision(
            request_id=context.request_id,
            capability=context.capability,
            mode=context.mode,
            allowed=allowed,
            blockers=tuple(dict.fromkeys(blockers)),
            required_scope=required_scope,
            environment=state.environment,
            external_execution_allowed=allowed,
            external_calls_made=0,
        )

    def require(self, context: ExecutionContext, *, required_scope: str) -> PolicyDecision:
        decision = self.evaluate(context, required_scope=required_scope)
        if not decision.allowed:
            raise PolicyGateError('Execution blocked by central policy gate: ' + ', '.join(decision.blockers))
        return decision

    def snapshot(self) -> dict:
        return {'policy': asdict(self._state), 'external_calls_made': 0}
