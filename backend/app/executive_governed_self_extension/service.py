from datetime import datetime, timezone
from uuid import UUID

from .models import (
    ChangePlanStep,
    CodeChangeExecuteRequest,
    CodeChangePlan,
    CodeChangeRequest,
    SelfExtensionAudit,
    SelfExtensionState,
    SelfExtensionStatus,
)


class GovernedSelfExtensionService:
    def __init__(self) -> None:
        self._plans: dict[UUID, CodeChangePlan] = {}
        self._source_keys: set[tuple[str, str]] = set()
        self._audit: list[SelfExtensionAudit] = []

    def create(self, payload: CodeChangeRequest) -> CodeChangePlan:
        key = (payload.workspace_id, payload.source_key)
        if key in self._source_keys:
            raise ValueError("duplicate source_key in workspace")

        state, detail = self._initial_state(payload)
        branch_name = self._branch_name(payload)
        steps = self._build_steps(payload) if state not in {SelfExtensionState.BLOCKED, SelfExtensionState.EVIDENCE_REQUIRED} else []
        plan = CodeChangePlan(
            workspace_id=payload.workspace_id,
            source_key=payload.source_key,
            state=state,
            detail=detail,
            request=payload,
            branch_name=branch_name,
            steps=steps,
            risk_level=self._risk_level(payload),
            required_checks=self._checks(payload),
            rollback_plan=self._rollback(payload),
        )
        self._plans[plan.id] = plan
        self._source_keys.add(key)
        self._log(plan, payload.actor_id, "create")
        return plan

    @staticmethod
    def _initial_state(payload: CodeChangeRequest):
        if payload.upstream_risk_brain_blocked:
            return SelfExtensionState.BLOCKED, "upstream Risk Brain hard block"
        if not payload.jarvis_core_approved_v20_00:
            return SelfExtensionState.EVIDENCE_REQUIRED, "v20.00 JARVIS Core approval required"
        if payload.human_approved:
            return SelfExtensionState.APPROVED, "change plan approved for controlled implementation"
        return SelfExtensionState.APPROVAL_REQUIRED, "human approval required before implementation"

    @staticmethod
    def _branch_name(payload: CodeChangeRequest) -> str:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in payload.target_module).strip("-")
        return f"jarvis-change-{slug[:48]}"

    @staticmethod
    def _risk_level(payload: CodeChangeRequest) -> str:
        text = f"{payload.target_module} {' '.join(payload.requested_changes)}".lower()
        if any(term in text for term in ("risk", "execution", "live", "broker", "kill switch")):
            return "high"
        if any(term in text for term in ("parameter", "config", "api", "router")):
            return "medium"
        return "low"

    @staticmethod
    def _build_steps(payload: CodeChangeRequest) -> list[ChangePlanStep]:
        steps = [
            ChangePlanStep(order=1, action="inspect", target=payload.target_module, validation="resolve files and dependencies"),
            ChangePlanStep(order=2, action="design", target=payload.target_module, validation="produce bounded diff plan"),
            ChangePlanStep(order=3, action="implement", target=payload.target_module, validation="write only on dedicated branch"),
        ]
        if payload.tests_required:
            steps.append(ChangePlanStep(order=4, action="test", target=payload.target_module, validation="unit and regression tests must pass"))
        steps.append(ChangePlanStep(order=len(steps) + 1, action="review", target="pull-request", validation="human reviews diff, risks and checks"))
        return steps

    @staticmethod
    def _checks(payload: CodeChangeRequest) -> list[str]:
        checks = ["syntax", "imports", "protected-path policy", "unsafe-command scan", "diff review"]
        if payload.tests_required:
            checks.extend(["unit tests", "regression tests", "Backend CI"])
        return checks

    @staticmethod
    def _rollback(payload: CodeChangeRequest) -> list[str]:
        if not payload.rollback_required:
            return []
        return ["preserve base commit SHA", "keep changes isolated on branch", "revert commit or close PR on failed validation"]

    def execute(self, plan_id: UUID, workspace_id: str, request: CodeChangeExecuteRequest) -> CodeChangePlan:
        plan = self.get(plan_id, workspace_id)
        if plan is None:
            raise KeyError("change plan not found")
        if plan.state in {SelfExtensionState.BLOCKED, SelfExtensionState.EVIDENCE_REQUIRED, SelfExtensionState.FAILED}:
            raise ValueError("action unavailable from current state")
        approved = request.human_approved if request.human_approved is not None else plan.request.human_approved
        if request.action in {"approve", "mark-implementation-ready"} and not approved:
            raise ValueError("human approval required")
        if request.action == "approve":
            plan.state, plan.detail = SelfExtensionState.APPROVED, "change plan approved"
        elif request.action == "mark-implementation-ready":
            if plan.state != SelfExtensionState.APPROVED:
                raise ValueError("plan must be approved first")
            plan.state, plan.detail = SelfExtensionState.IMPLEMENTATION_READY, "controlled branch implementation may begin"
        else:
            plan.state, plan.detail = SelfExtensionState.ARCHIVED, "change plan archived"
        plan.updated_at = datetime.now(timezone.utc)
        self._log(plan, request.actor_id, request.action)
        return plan

    def get(self, plan_id: UUID, workspace_id: str) -> CodeChangePlan | None:
        plan = self._plans.get(plan_id)
        return plan if plan and plan.workspace_id == workspace_id else None

    def list_plans(self, workspace_id: str) -> list[CodeChangePlan]:
        return [plan for plan in self._plans.values() if plan.workspace_id == workspace_id]

    def status(self, workspace_id: str) -> SelfExtensionStatus:
        plans = self.list_plans(workspace_id)
        approved = {SelfExtensionState.APPROVED, SelfExtensionState.IMPLEMENTATION_READY}
        blocked = {SelfExtensionState.BLOCKED, SelfExtensionState.EVIDENCE_REQUIRED, SelfExtensionState.FAILED}
        return SelfExtensionStatus(
            workspace_id=workspace_id,
            total_plans=len(plans),
            approved_plans=sum(plan.state in approved for plan in plans),
            blocked_plans=sum(plan.state in blocked for plan in plans),
        )

    def audit_records(self, workspace_id: str) -> list[SelfExtensionAudit]:
        return [item for item in self._audit if item.workspace_id == workspace_id]

    def _log(self, plan: CodeChangePlan, actor_id: str, action: str) -> None:
        self._audit.append(SelfExtensionAudit(
            plan_id=plan.id,
            workspace_id=plan.workspace_id,
            actor_id=actor_id,
            action=action,
            state=plan.state,
            detail=plan.detail,
        ))


governed_self_extension_service = GovernedSelfExtensionService()
