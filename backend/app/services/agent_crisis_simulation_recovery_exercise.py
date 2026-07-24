from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import mean
from typing import Dict, List, Set, Tuple
from uuid import uuid4

from app.schemas.agent_crisis_simulation_recovery_exercise import (
    CrisisExerciseCreate, CrisisExerciseDisposition, CrisisExerciseRecord,
    CrisisExerciseScores, CrisisExerciseState,
)


@dataclass
class AuditEntry:
    audit_id: str
    workspace_id: str
    record_id: str
    action: str
    actor: str
    operation_id: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


class AgentCrisisSimulationRecoveryExerciseService:
    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], CrisisExerciseRecord] = {}
        self._source_keys: Set[Tuple[str, str]] = set()
        self._operations: Set[Tuple[str, str]] = set()
        self._audit: List[AuditEntry] = []

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 4)

    def status(self) -> dict:
        return {
            "module": "agent-crisis-simulation-recovery-exercise-governance",
            "version": "21.105",
            "governance_only": True,
            "scenario_execution_enabled": False,
            "fault_injection_enabled": False,
            "automatic_failover_enabled": False,
            "automatic_recovery_enabled": False,
            "traffic_shift_enabled": False,
            "agent_execution_enabled": False,
            "trading_execution_enabled": False,
            "human_approval_required": True,
            "risk_brain_authoritative": True,
        }

    def create(self, payload: CrisisExerciseCreate) -> CrisisExerciseRecord:
        source = (payload.workspace_id, payload.source_key)
        if source in self._source_keys:
            raise ValueError("duplicate source_key for workspace")
        scores, dispositions, flags = self._assess(payload)
        state = CrisisExerciseState.BLOCKED if "risk-brain-hard-block" in flags else CrisisExerciseState.EVIDENCE_READY
        record = CrisisExerciseRecord(
            record_id=str(uuid4()), workspace_id=payload.workspace_id, source_key=payload.source_key,
            state=state, scores=scores, dispositions=dispositions, risk_flags=flags,
        )
        self._records[(payload.workspace_id, record.record_id)] = record
        self._source_keys.add(source)
        self._audit_event(record, "create", payload.requested_by, f"create:{record.record_id}")
        return record

    def list(self, workspace_id: str) -> List[CrisisExerciseRecord]:
        return [r for (ws, _), r in self._records.items() if ws == workspace_id]

    def get(self, workspace_id: str, record_id: str) -> CrisisExerciseRecord:
        try:
            return self._records[(workspace_id, record_id)]
        except KeyError as exc:
            raise KeyError("record not found") from exc

    def act(self, workspace_id: str, record_id: str, action: str, actor: str, operation_id: str, reason: str | None = None) -> CrisisExerciseRecord:
        receipt = (workspace_id, operation_id)
        if receipt in self._operations:
            raise ValueError("operation replay detected")
        record = self.get(workspace_id, record_id)
        transitions = {
            "assess": CrisisExerciseState.ASSESSED,
            "submit-review": CrisisExerciseState.REVIEW_REQUIRED,
            "approve": CrisisExerciseState.APPROVED,
            "activate": CrisisExerciseState.ACTIVE,
            "monitor": CrisisExerciseState.MONITORING,
            "verify": CrisisExerciseState.VERIFIED,
            "suspend": CrisisExerciseState.SUSPENDED,
            "revoke": CrisisExerciseState.REVOKED,
            "archive": CrisisExerciseState.ARCHIVED,
        }
        if action not in transitions:
            raise ValueError("unsupported action")
        if action == "approve" and record.risk_flags:
            raise ValueError("unresolved crisis-exercise findings block approval")
        if action in {"activate", "monitor", "verify"} and record.state not in {
            CrisisExerciseState.APPROVED, CrisisExerciseState.ACTIVE,
            CrisisExerciseState.MONITORING, CrisisExerciseState.VERIFIED,
        }:
            raise ValueError("human approval required before governed active state")
        updated = record.model_copy(update={
            "state": transitions[action],
            "approved_by": actor if action == "approve" else record.approved_by,
            "version": record.version + 1,
        })
        self._records[(workspace_id, record_id)] = updated
        self._operations.add(receipt)
        self._audit_event(updated, action, actor, operation_id, {"reason": reason} if reason else {})
        return updated

    def audit(self, workspace_id: str) -> List[AuditEntry]:
        return [e for e in self._audit if e.workspace_id == workspace_id]

    def _assess(self, payload: CrisisExerciseCreate):
        obs = payload.observations
        scenario = mean((o.scenario_coverage + o.severity_realism) / 2 for o in obs)
        command = mean((o.incident_command_readiness + o.decision_timing_quality) / 2 for o in obs)
        recovery = mean((o.recovery_sequence_quality + o.rto_attainment + o.rpo_attainment + o.dependency_coordination) / 4 for o in obs)
        communication = mean(o.communication_readiness for o in obs)
        runbook = mean(o.runbook_effectiveness for o in obs)
        learning = mean((o.evidence_capture + o.lessons_learned_quality) / 2 for o in obs)
        confidence = mean(o.confidence * o.freshness for o in obs)
        aggregate = self._clamp(mean([scenario, command, recovery, communication, runbook, learning]) * confidence)
        aggregate_risk = self._clamp(mean(
            (1-o.scenario_coverage)*0.08 + (1-o.incident_command_readiness)*0.12 +
            (1-o.decision_timing_quality)*0.08 + (1-o.communication_readiness)*0.08 +
            (1-o.recovery_sequence_quality)*0.12 + (1-o.rto_attainment)*0.10 +
            (1-o.rpo_attainment)*0.10 + (1-o.dependency_coordination)*0.08 +
            (1-o.runbook_effectiveness)*0.08 + (1-o.lessons_learned_quality)*0.06 +
            min(o.failed_command_decisions/3,1)*0.04 + min(o.missed_recovery_objectives/3,1)*0.04 +
            min(o.communication_failures/3,1)*0.01 + min(o.unresolved_lessons/3,1)*0.01
            for o in obs
        ))
        scores = CrisisExerciseScores(
            scenario_assurance=self._clamp(scenario), command_assurance=self._clamp(command),
            recovery_assurance=self._clamp(recovery), communication_assurance=self._clamp(communication),
            runbook_assurance=self._clamp(runbook), learning_assurance=self._clamp(learning),
            aggregate_assurance=aggregate, aggregate_residual_risk=aggregate_risk,
            confidence=self._clamp(confidence),
        )
        dispositions: List[CrisisExerciseDisposition] = []
        flags: List[str] = []
        for o in obs:
            actions: List[str] = []
            signal = "verified"
            residual = self._clamp(
                (1-o.scenario_coverage)*0.10 + (1-o.incident_command_readiness)*0.14 +
                (1-o.decision_timing_quality)*0.08 + (1-o.communication_readiness)*0.08 +
                (1-o.recovery_sequence_quality)*0.14 + (1-o.rto_attainment)*0.10 +
                (1-o.rpo_attainment)*0.10 + (1-o.dependency_coordination)*0.08 +
                (1-o.runbook_effectiveness)*0.08 + (1-o.lessons_learned_quality)*0.05 +
                min(o.failed_command_decisions/3,1)*0.02 + min(o.missed_recovery_objectives/3,1)*0.02 +
                min(o.communication_failures/3,1)*0.005 + min(o.unresolved_lessons/3,1)*0.005
            )
            if o.scenario_coverage < payload.min_scenario_coverage:
                signal = "scenario-alert"; actions.append("crisis-scenario-coverage-review"); flags.append(f"scenario-alert:{o.agent_id}:{o.exercise_id}")
            if o.incident_command_readiness < payload.min_command_readiness or o.failed_command_decisions > 0:
                signal = "command-alert"; actions.append("incident-command-decision-review"); flags.append(f"command-alert:{o.agent_id}:{o.exercise_id}")
            recovery_floor = min(o.recovery_sequence_quality, o.rto_attainment, o.rpo_attainment)
            if recovery_floor < payload.min_recovery_quality or o.missed_recovery_objectives > 0:
                signal = "recovery-alert"; actions.append("recovery-objective-exercise-review"); flags.append(f"recovery-alert:{o.agent_id}:{o.exercise_id}")
            if o.communication_readiness < payload.min_communication_readiness or o.communication_failures > 0:
                signal = "communication-alert"; actions.append("crisis-communication-review"); flags.append(f"communication-alert:{o.agent_id}:{o.exercise_id}")
            if o.lessons_learned_quality < 0.80 or o.unresolved_lessons > 0:
                signal = "lessons-alert"; actions.append("exercise-lessons-and-remediation-review"); flags.append(f"lessons-alert:{o.agent_id}:{o.exercise_id}")
            if residual > payload.max_residual_risk:
                actions.append("crisis-exercise-risk-committee"); flags.append(f"residual-risk-breach:{o.agent_id}:{o.exercise_id}")
            if o.business_criticality >= 0.90 and (o.failed_command_decisions > 0 or o.missed_recovery_objectives > 0 or residual >= 0.60):
                signal = "recovery-alert"; actions.append("risk-brain-hard-block"); flags.append("risk-brain-hard-block")
            dispositions.append(CrisisExerciseDisposition(
                agent_id=o.agent_id, agent_version=o.agent_version, exercise_id=o.exercise_id,
                assurance=self._clamp(1-residual), residual_risk=residual,
                lifecycle_signal=signal, required_actions=sorted(set(actions)),
            ))
        return scores, dispositions, sorted(set(flags))

    def _audit_event(self, record: CrisisExerciseRecord, action: str, actor: str, operation_id: str, metadata: dict | None = None) -> None:
        self._audit.append(AuditEntry(
            audit_id=str(uuid4()), workspace_id=record.workspace_id, record_id=record.record_id,
            action=action, actor=actor, operation_id=operation_id,
            timestamp=datetime.now(timezone.utc).isoformat(), metadata=metadata or {},
        ))


agent_crisis_simulation_recovery_exercise_service = AgentCrisisSimulationRecoveryExerciseService()
