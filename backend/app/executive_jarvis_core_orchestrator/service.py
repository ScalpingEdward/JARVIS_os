from datetime import datetime, timezone
from uuid import UUID

from .models import (
    JarvisCoreAudit,
    JarvisCoreCreate,
    JarvisCoreExecuteRequest,
    JarvisCoreRecord,
    JarvisCoreState,
    JarvisCoreStatus,
    OrchestrationStep,
)


class JarvisCoreOrchestratorService:
    def __init__(self) -> None:
        self._records: dict[UUID, JarvisCoreRecord] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[JarvisCoreAudit] = []

    def create(self, payload: JarvisCoreCreate) -> JarvisCoreRecord:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")
        state, detail, plan, blocked = self._evaluate(payload)
        record = JarvisCoreRecord(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            plan=plan,
            blocked_modules=blocked,
        )
        self._records[record.id] = record
        self._source_keys.add(key)
        self._log(record, payload.actor_id, "create")
        return record

    def _evaluate(self, payload: JarvisCoreCreate):
        if payload.upstream_risk_brain_blocked:
            return JarvisCoreState.BLOCKED, "upstream Risk Brain hard block", [], ["risk-brain"]

        evidence = {
            "v19.08": payload.market_permission_v19_08,
            "v19.09": payload.shadow_validation_v19_09,
            "v19.10": payload.journal_validation_v19_10,
            "v19.11": payload.optimizer_approval_v19_11,
            "v19.12": payload.governor_clearance_v19_12,
        }
        missing = [name for name, ok in evidence.items() if not ok]
        if missing:
            return JarvisCoreState.EVIDENCE_REQUIRED, f"missing upstream evidence: {', '.join(missing)}", [], missing

        forbidden = []
        for command in payload.commands:
            action = command.action.lower()
            if any(token in action for token in ("increase-risk", "relax-limit", "bypass", "force-live")):
                forbidden.append(command.module)
        if forbidden:
            return JarvisCoreState.BLOCKED, "unsafe command requires redesign and explicit governance", [], forbidden

        plan = [
            OrchestrationStep(order=index, module=command.module, action=command.action)
            for index, command in enumerate(payload.commands, start=1)
        ]
        requires_approval = any(command.requires_human_approval and not command.protective_only for command in payload.commands)
        state = JarvisCoreState.APPROVAL_REQUIRED if requires_approval and not payload.human_approved else JarvisCoreState.READY
        detail = "human approval required before orchestration" if state == JarvisCoreState.APPROVAL_REQUIRED else "orchestration plan validated and ready"
        return state, detail, plan, []

    def execute(self, record_id: UUID, workspace_id: str, request: JarvisCoreExecuteRequest) -> JarvisCoreRecord:
        record = self.get(record_id, workspace_id)
        if record is None:
            raise KeyError("JARVIS core record not found")
        approved = request.human_approved if request.human_approved is not None else record.request.human_approved

        if request.action in {"approve", "execute"} and not approved:
            raise ValueError("human approval required")
        if record.state in {JarvisCoreState.BLOCKED, JarvisCoreState.EVIDENCE_REQUIRED, JarvisCoreState.INPUT_INVALID, JarvisCoreState.FAILED}:
            raise ValueError("orchestration action unavailable from current state")

        if request.action == "approve":
            record.state, record.detail = JarvisCoreState.READY, "orchestration approved"
        elif request.action == "execute":
            record.state, record.detail = JarvisCoreState.EXECUTING, "governed orchestration started"
            for step in record.plan:
                step.status = "dispatched"
                step.detail = "command handed to governed module boundary"
        elif request.action == "complete":
            if record.state != JarvisCoreState.EXECUTING:
                raise ValueError("record must be executing before completion")
            for step in record.plan:
                step.status = "completed"
                step.detail = "module reported governed completion"
            record.state, record.detail = JarvisCoreState.COMPLETED, "orchestration completed"
        elif request.action == "archive":
            record.state, record.detail = JarvisCoreState.ARCHIVED, "orchestration archived"

        record.updated_at = datetime.now(timezone.utc)
        self._log(record, request.actor_id, request.action)
        return record

    def get(self, record_id: UUID, workspace_id: str) -> JarvisCoreRecord | None:
        record = self._records.get(record_id)
        return record if record and record.workspace_id == workspace_id else None

    def list_records(self, workspace_id: str) -> list[JarvisCoreRecord]:
        return [record for record in self._records.values() if record.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> JarvisCoreStatus:
        records = self.list_records(workspace_id)
        active = {JarvisCoreState.READY, JarvisCoreState.EXECUTING, JarvisCoreState.COMPLETED}
        blocked = {JarvisCoreState.BLOCKED, JarvisCoreState.EVIDENCE_REQUIRED, JarvisCoreState.FAILED}
        return JarvisCoreStatus(
            workspace_id=workspace_id,
            total_records=len(records),
            active_records=sum(record.state in active for record in records),
            blocked_records=sum(record.state in blocked for record in records),
        )

    def audit_records(self, workspace_id: str) -> list[JarvisCoreAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, record: JarvisCoreRecord, actor_id: str, action: str) -> None:
        self._audit.append(JarvisCoreAudit(
            record_id=record.id,
            workspace_id=record.workspace_id,
            actor_id=actor_id,
            action=action,
            state=record.state,
            detail=record.detail,
        ))


jarvis_core_orchestrator_service = JarvisCoreOrchestratorService()
