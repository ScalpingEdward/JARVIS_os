from datetime import datetime, timedelta, timezone
from uuid import UUID

from .models import (
    ApprovalDecisionCreate, ApprovalDecisionRecord, ApprovalRequestCreate,
    ApprovalRequestRecord, AuditRecord, DecisionType, EvaluationRecord,
    EvaluationRequest, ExceptionCreate, ExceptionDecision, ExceptionRecord,
    ExceptionState, PolicyApprovalStatus, PolicyCreate, PolicyEffect,
    PolicyMutation, PolicyRecord, PolicyState, RequestState, RiskClass,
)


_RISK_ORDER = {RiskClass.LOW: 0, RiskClass.MEDIUM: 1, RiskClass.HIGH: 2, RiskClass.CRITICAL: 3}


class PolicyApprovalService:
    def __init__(self) -> None:
        self.policies: dict[UUID, PolicyRecord] = {}
        self.evaluations: dict[UUID, EvaluationRecord] = {}
        self.requests: dict[UUID, ApprovalRequestRecord] = {}
        self.decisions: dict[UUID, ApprovalDecisionRecord] = {}
        self.exceptions: dict[UUID, ExceptionRecord] = {}
        self.audit: list[AuditRecord] = []

    def _audit(self, workspace_id: str, actor_id: str, event_type: str, resource_type: str, resource_id: str, **details) -> None:
        self.audit.append(AuditRecord(workspace_id=workspace_id, actor_id=actor_id, event_type=event_type, resource_type=resource_type, resource_id=resource_id, details=details))

    def status(self) -> PolicyApprovalStatus:
        now = datetime.now(timezone.utc)
        self._expire(now)
        return PolicyApprovalStatus(
            policies=len(self.policies),
            pending_requests=sum(item.state == RequestState.PENDING for item in self.requests.values()),
            open_exceptions=sum(item.state in {ExceptionState.REQUESTED, ExceptionState.GRANTED} for item in self.exceptions.values()),
        )

    def create_policy(self, payload: PolicyCreate) -> PolicyRecord:
        if any(item.workspace_id == payload.workspace_id and item.policy_key == payload.policy_key and item.state != PolicyState.RETIRED for item in self.policies.values()):
            raise ValueError("active policy key already exists")
        record = PolicyRecord(**payload.model_dump())
        self.policies[record.id] = record
        self._audit(record.workspace_id, record.owner_id, "policy.created", "policy", str(record.id))
        return record

    def list_policies(self, workspace_id: str) -> list[PolicyRecord]:
        return sorted((item for item in self.policies.values() if item.workspace_id == workspace_id), key=lambda item: (item.priority, item.policy_key))

    def get_policy(self, policy_id: UUID, workspace_id: str) -> PolicyRecord | None:
        item = self.policies.get(policy_id)
        return item if item and item.workspace_id == workspace_id else None

    def set_policy_state(self, policy_id: UUID, workspace_id: str, payload: PolicyMutation, state: PolicyState) -> PolicyRecord | None:
        item = self.get_policy(policy_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id:
            return None
        item.state = state
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, f"policy.{state.value}", "policy", str(policy_id), reason=payload.reason)
        return item

    def evaluate(self, payload: EvaluationRequest) -> EvaluationRecord:
        matches = []
        for item in self.policies.values():
            if item.workspace_id != payload.workspace_id or item.state != PolicyState.ACTIVE:
                continue
            if item.target_modules and payload.source_module not in item.target_modules:
                continue
            if item.target_actions and payload.action not in item.target_actions:
                continue
            if _RISK_ORDER[payload.risk_class] < _RISK_ORDER[item.minimum_risk]:
                continue
            matches.append(item)
        matches.sort(key=lambda item: item.priority)
        effect = PolicyEffect.ALLOW
        required = 0
        reason = "no active policy matched; safe default allow for internal planning"
        if matches:
            deny = next((item for item in matches if item.effect == PolicyEffect.DENY), None)
            approval = next((item for item in matches if item.effect == PolicyEffect.REQUIRE_APPROVAL), None)
            if deny:
                effect, reason = PolicyEffect.DENY, f"denied by policy {deny.policy_key}"
            elif approval:
                effect = PolicyEffect.REQUIRE_APPROVAL
                required = max(item.required_approvals for item in matches if item.effect == PolicyEffect.REQUIRE_APPROVAL)
                reason = "human approval required by active policy"
            else:
                reason = "allowed by active policy"
        record = EvaluationRecord(
            workspace_id=payload.workspace_id, requester_id=payload.requester_id,
            source_module=payload.source_module, action=payload.action,
            risk_class=payload.risk_class, matched_policy_ids=[item.id for item in matches],
            effect=effect, allowed=effect == PolicyEffect.ALLOW,
            approval_required=effect == PolicyEffect.REQUIRE_APPROVAL,
            required_approvals=required, reason=reason,
        )
        self.evaluations[record.id] = record
        self._audit(payload.workspace_id, payload.requester_id, "policy.evaluated", "evaluation", str(record.id), effect=effect.value)
        return record

    def list_evaluations(self, workspace_id: str) -> list[EvaluationRecord]:
        return [item for item in self.evaluations.values() if item.workspace_id == workspace_id]

    def create_request(self, payload: ApprovalRequestCreate) -> ApprovalRequestRecord:
        record = ApprovalRequestRecord(**payload.model_dump(), expires_at=datetime.now(timezone.utc) + timedelta(minutes=payload.ttl_minutes))
        self.requests[record.id] = record
        self._audit(record.workspace_id, record.requester_id, "approval.requested", "approval_request", str(record.id))
        return record

    def list_requests(self, workspace_id: str) -> list[ApprovalRequestRecord]:
        self._expire(datetime.now(timezone.utc))
        return [item for item in self.requests.values() if item.workspace_id == workspace_id]

    def get_request(self, request_id: UUID, workspace_id: str) -> ApprovalRequestRecord | None:
        self._expire(datetime.now(timezone.utc))
        item = self.requests.get(request_id)
        return item if item and item.workspace_id == workspace_id else None

    def decide(self, payload: ApprovalDecisionCreate) -> ApprovalRequestRecord | None:
        request = self.get_request(payload.request_id, payload.workspace_id)
        if request is None or request.state != RequestState.PENDING:
            return None
        prior = [item for item in self.decisions.values() if item.request_id == request.id]
        if request.require_distinct_approvers and any(item.approver_id == payload.approver_id for item in prior):
            raise ValueError("approver has already decided")
        if payload.approver_id == request.requester_id:
            raise ValueError("requester cannot approve their own request")
        decision = ApprovalDecisionRecord(**payload.model_dump())
        self.decisions[decision.id] = decision
        if payload.decision == DecisionType.REJECT:
            request.rejected_count += 1
            request.state = RequestState.REJECTED
        else:
            request.approved_count += 1
            if request.approved_count >= request.required_approvals:
                request.state = RequestState.APPROVED
        request.updated_at = datetime.now(timezone.utc)
        self._audit(request.workspace_id, payload.approver_id, f"approval.{payload.decision.value}", "approval_request", str(request.id), approved_count=request.approved_count)
        return request

    def cancel_request(self, request_id: UUID, workspace_id: str, payload: PolicyMutation) -> ApprovalRequestRecord | None:
        item = self.get_request(request_id, workspace_id)
        if item is None or item.owner_id != payload.requester_id or item.state != RequestState.PENDING:
            return None
        item.state = RequestState.CANCELLED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, "approval.cancelled", "approval_request", str(request_id), reason=payload.reason)
        return item

    def list_decisions(self, workspace_id: str, request_id: UUID | None = None) -> list[ApprovalDecisionRecord]:
        return [item for item in self.decisions.values() if item.workspace_id == workspace_id and (request_id is None or item.request_id == request_id)]

    def create_exception(self, payload: ExceptionCreate) -> ExceptionRecord:
        policy = self.get_policy(payload.policy_id, payload.workspace_id)
        if policy is None:
            raise ValueError("policy not found")
        record = ExceptionRecord(**payload.model_dump())
        self.exceptions[record.id] = record
        self._audit(record.workspace_id, record.requester_id, "exception.requested", "exception", str(record.id))
        return record

    def decide_exception(self, exception_id: UUID, workspace_id: str, payload: ExceptionDecision) -> ExceptionRecord | None:
        item = self.exceptions.get(exception_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id or item.state != ExceptionState.REQUESTED:
            return None
        item.state = ExceptionState.GRANTED if payload.grant else ExceptionState.REJECTED
        item.granted_by = payload.requester_id if payload.grant else None
        item.expires_at = datetime.now(timezone.utc) + timedelta(minutes=item.ttl_minutes) if payload.grant else None
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, f"exception.{item.state.value}", "exception", str(exception_id), reason=payload.reason)
        return item

    def revoke_exception(self, exception_id: UUID, workspace_id: str, payload: PolicyMutation) -> ExceptionRecord | None:
        item = self.exceptions.get(exception_id)
        if item is None or item.workspace_id != workspace_id or item.owner_id != payload.requester_id or item.state != ExceptionState.GRANTED:
            return None
        item.state = ExceptionState.REVOKED
        item.updated_at = datetime.now(timezone.utc)
        self._audit(workspace_id, payload.requester_id, "exception.revoked", "exception", str(exception_id), reason=payload.reason)
        return item

    def list_exceptions(self, workspace_id: str) -> list[ExceptionRecord]:
        self._expire(datetime.now(timezone.utc))
        return [item for item in self.exceptions.values() if item.workspace_id == workspace_id]

    def list_audit(self, workspace_id: str) -> list[AuditRecord]:
        return [item for item in self.audit if item.workspace_id == workspace_id]

    def _expire(self, now: datetime) -> None:
        for item in self.requests.values():
            if item.state == RequestState.PENDING and item.expires_at <= now:
                item.state = RequestState.EXPIRED
                item.updated_at = now
        for item in self.exceptions.values():
            if item.state == ExceptionState.GRANTED and item.expires_at and item.expires_at <= now:
                item.state = ExceptionState.EXPIRED
                item.updated_at = now


policy_approval_service = PolicyApprovalService()
