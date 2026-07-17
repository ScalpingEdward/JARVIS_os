from copy import deepcopy
from datetime import datetime, timezone
from random import Random
from uuid import UUID

from .models import (
    AdapterRecord,
    AdapterRegister,
    ScenarioCreate,
    ScenarioMutation,
    ScenarioRecord,
    ScenarioState,
    ScenarioValidation,
    SimulationCreate,
    SimulationLabStatus,
    SimulationRecord,
    SimulationState,
    StepResult,
)


class ConnectorSimulationService:
    def __init__(self) -> None:
        self._adapters: dict[UUID, AdapterRecord] = {}
        self._scenarios: dict[UUID, ScenarioRecord] = {}
        self._simulations: dict[UUID, SimulationRecord] = {}

    def status(self) -> SimulationLabStatus:
        simulations = list(self._simulations.values())
        return SimulationLabStatus(
            registered_adapters=len(self._adapters),
            ready_scenarios=sum(item.state == ScenarioState.READY for item in self._scenarios.values()),
            total_simulations=len(simulations),
            passed_simulations=sum(item.state == SimulationState.PASSED for item in simulations),
            failed_simulations=sum(item.state == SimulationState.FAILED for item in simulations),
        )

    def register_adapter(self, payload: AdapterRegister) -> AdapterRecord:
        duplicate = any(
            item.workspace_id == payload.workspace_id and item.adapter_key == payload.adapter_key
            for item in self._adapters.values()
        )
        if duplicate:
            raise ValueError("adapter key already exists in workspace")
        record = AdapterRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            adapter_key=payload.adapter_key.strip().lower(),
            adapter_type=payload.adapter_type,
            display_name=payload.display_name.strip(),
            version=payload.version.strip(),
            actions=payload.actions,
        )
        self._adapters[record.id] = record
        return record

    def list_adapters(self, workspace_id: str) -> list[AdapterRecord]:
        return sorted(
            [item for item in self._adapters.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def get_adapter(self, adapter_id: UUID, workspace_id: str) -> AdapterRecord | None:
        record = self._adapters.get(adapter_id)
        return record if record and record.workspace_id == workspace_id else None

    def create_scenario(self, payload: ScenarioCreate) -> ScenarioRecord:
        record = ScenarioRecord(
            workspace_id=payload.workspace_id.strip(),
            owner_id=payload.owner_id.strip(),
            name=payload.name.strip(),
            description=payload.description.strip(),
            steps=payload.steps,
        )
        validation = self._validate(record)
        record.validation_errors = validation.errors
        self._scenarios[record.id] = record
        return record

    def list_scenarios(self, workspace_id: str) -> list[ScenarioRecord]:
        return sorted(
            [item for item in self._scenarios.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
        )

    def get_scenario(self, scenario_id: UUID, workspace_id: str) -> ScenarioRecord | None:
        record = self._scenarios.get(scenario_id)
        return record if record and record.workspace_id == workspace_id else None

    def validate_scenario(self, scenario_id: UUID, workspace_id: str) -> ScenarioValidation | None:
        record = self.get_scenario(scenario_id, workspace_id)
        if record is None:
            return None
        validation = self._validate(record)
        record.validation_errors = validation.errors
        record.updated_at = datetime.now(timezone.utc)
        return validation

    def mark_ready(
        self,
        scenario_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: ScenarioMutation,
    ) -> ScenarioRecord | None:
        record = self.get_scenario(scenario_id, workspace_id)
        if record is None or record.owner_id != requester_id:
            return None
        validation = self._validate(record)
        record.validation_errors = validation.errors
        if not validation.valid:
            return record
        record.state = ScenarioState.READY
        record.updated_at = datetime.now(timezone.utc)
        return record

    def archive_scenario(
        self,
        scenario_id: UUID,
        workspace_id: str,
        requester_id: str,
        payload: ScenarioMutation,
    ) -> ScenarioRecord | None:
        record = self.get_scenario(scenario_id, workspace_id)
        if record is None or record.owner_id != requester_id:
            return None
        record.state = ScenarioState.ARCHIVED
        record.updated_at = datetime.now(timezone.utc)
        return record

    def run_simulation(self, scenario_id: UUID, payload: SimulationCreate) -> SimulationRecord | None:
        scenario = self.get_scenario(scenario_id, payload.workspace_id)
        if scenario is None or scenario.state != ScenarioState.READY:
            return None
        validation = self._validate(scenario)
        if not validation.valid:
            return None
        simulation = SimulationRecord(
            workspace_id=payload.workspace_id,
            requester_id=payload.requester_id,
            scenario_id=scenario.id,
            seed=payload.seed,
            context=deepcopy(payload.context),
            state=SimulationState.RUNNING,
            started_at=datetime.now(timezone.utc),
        )
        rng = Random(payload.seed)
        by_key = {step.key: step for step in scenario.steps}
        results: dict[str, StepResult] = {}
        for key in validation.execution_order:
            step = by_key[key]
            now = datetime.now(timezone.utc)
            adapter = self.get_adapter(step.adapter_id, payload.workspace_id)
            error = self._validate_step_runtime(step, adapter, results)
            if error:
                result = StepResult(
                    step_key=key,
                    adapter_id=step.adapter_id,
                    action=step.action,
                    state=SimulationState.FAILED,
                    input=deepcopy(step.input),
                    error=error,
                    started_at=now,
                    completed_at=datetime.now(timezone.utc),
                )
                results[key] = result
                simulation.step_results.append(result)
                simulation.trace.append(f"{key}:failed:{error}")
                simulation.state = SimulationState.FAILED
                break
            output = self._simulate_output(step.action, step.input, step.expected_output, rng)
            result = StepResult(
                step_key=key,
                adapter_id=step.adapter_id,
                action=step.action,
                state=SimulationState.PASSED,
                input=deepcopy(step.input),
                output=output,
                started_at=now,
                completed_at=datetime.now(timezone.utc),
            )
            results[key] = result
            simulation.step_results.append(result)
            simulation.trace.append(f"{key}:passed")
            simulation.context[key] = output
        if simulation.state != SimulationState.FAILED:
            simulation.state = SimulationState.PASSED
        simulation.completed_at = datetime.now(timezone.utc)
        self._simulations[simulation.id] = simulation
        return simulation

    def list_simulations(self, workspace_id: str) -> list[SimulationRecord]:
        return sorted(
            [item for item in self._simulations.values() if item.workspace_id == workspace_id],
            key=lambda item: item.created_at,
            reverse=True,
        )

    def get_simulation(self, simulation_id: UUID, workspace_id: str) -> SimulationRecord | None:
        record = self._simulations.get(simulation_id)
        return record if record and record.workspace_id == workspace_id else None

    def _validate(self, scenario: ScenarioRecord) -> ScenarioValidation:
        errors: list[str] = []
        keys = [step.key for step in scenario.steps]
        if len(keys) != len(set(keys)):
            errors.append("duplicate step keys")
        key_set = set(keys)
        for step in scenario.steps:
            if step.key in step.depends_on:
                errors.append(f"step {step.key} depends on itself")
            unknown = sorted(set(step.depends_on) - key_set)
            if unknown:
                errors.append(f"step {step.key} has unknown dependencies: {', '.join(unknown)}")
            adapter = self._adapters.get(step.adapter_id)
            if adapter is None or adapter.workspace_id != scenario.workspace_id:
                errors.append(f"step {step.key} references unavailable adapter")
            elif step.action not in {action.key for action in adapter.actions}:
                errors.append(f"step {step.key} uses unsupported action {step.action}")
        order: list[str] = []
        remaining = {step.key: set(step.depends_on) for step in scenario.steps}
        while remaining:
            ready = sorted(key for key, deps in remaining.items() if not deps)
            if not ready:
                errors.append("scenario contains a dependency cycle")
                break
            for key in ready:
                order.append(key)
                remaining.pop(key)
            for deps in remaining.values():
                deps.difference_update(ready)
        return ScenarioValidation(valid=not errors, errors=errors, execution_order=order if not errors else [])

    @staticmethod
    def _validate_step_runtime(step, adapter: AdapterRecord | None, results: dict[str, StepResult]) -> str | None:
        if adapter is None or not adapter.enabled:
            return "adapter unavailable"
        if any(results[item].state != SimulationState.PASSED for item in step.depends_on):
            return "dependency did not pass"
        action = next((item for item in adapter.actions if item.key == step.action), None)
        if action is None:
            return "action unavailable"
        missing = [field for field in action.required_fields if field not in step.input]
        if missing:
            return f"missing required fields: {', '.join(missing)}"
        return None

    @staticmethod
    def _simulate_output(action: str, input_data: dict, expected: dict, rng: Random) -> dict:
        output = deepcopy(expected)
        output.setdefault("dry_run", True)
        output.setdefault("action", action)
        output.setdefault("accepted", True)
        output.setdefault("simulation_id", f"sim-{rng.randint(100000, 999999)}")
        output.setdefault("input_echo", deepcopy(input_data))
        return output


connector_simulation_service = ConnectorSimulationService()
