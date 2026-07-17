from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from .models import (
    ApprovalDecisionCreate, ApprovalDecisionRecord, ApprovalRequestCreate,
    ApprovalRequestRecord, AuditRecord, EvaluationRecord, EvaluationRequest,
    ExceptionCreate, ExceptionDecision, ExceptionRecord, PolicyApprovalStatus,
    PolicyCreate, PolicyMutation, PolicyRecord, PolicyState,
)
from .service import policy_approval_service


router = APIRouter(prefix="/v1/policy-approval", tags=["policy-approval"])


@router.get("/status", response_model=PolicyApprovalStatus)
def get_status() -> PolicyApprovalStatus:
    return policy_approval_service.status()


@router.post("/policies", response_model=PolicyRecord, status_code=status.HTTP_201_CREATED)
def create_policy(payload: PolicyCreate) -> PolicyRecord:
    try:
        return policy_approval_service.create_policy(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/policies", response_model=list[PolicyRecord])
def list_policies(workspace_id: str = Query(min_length=1, max_length=120)) -> list[PolicyRecord]:
    return policy_approval_service.list_policies(workspace_id)


@router.get("/policies/{policy_id}", response_model=PolicyRecord)
def get_policy(policy_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    item = policy_approval_service.get_policy(policy_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    return item


def _set_policy(policy_id: UUID, workspace_id: str, payload: PolicyMutation, state: PolicyState) -> PolicyRecord:
    item = policy_approval_service.set_policy_state(policy_id, workspace_id, payload, state)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned policy not found")
    return item


@router.post("/policies/{policy_id}/activate", response_model=PolicyRecord)
def activate_policy(policy_id: UUID, payload: PolicyMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.ACTIVE)


@router.post("/policies/{policy_id}/retire", response_model=PolicyRecord)
def retire_policy(policy_id: UUID, payload: PolicyMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> PolicyRecord:
    return _set_policy(policy_id, workspace_id, payload, PolicyState.RETIRED)


@router.post("/evaluate", response_model=EvaluationRecord)
def evaluate(payload: EvaluationRequest) -> EvaluationRecord:
    return policy_approval_service.evaluate(payload)


@router.get("/evaluations", response_model=list[EvaluationRecord])
def list_evaluations(workspace_id: str = Query(min_length=1, max_length=120)) -> list[EvaluationRecord]:
    return policy_approval_service.list_evaluations(workspace_id)


@router.post("/requests", response_model=ApprovalRequestRecord, status_code=status.HTTP_201_CREATED)
def create_request(payload: ApprovalRequestCreate) -> ApprovalRequestRecord:
    return policy_approval_service.create_request(payload)


@router.get("/requests", response_model=list[ApprovalRequestRecord])
def list_requests(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ApprovalRequestRecord]:
    return policy_approval_service.list_requests(workspace_id)


@router.get("/requests/{request_id}", response_model=ApprovalRequestRecord)
def get_request(request_id: UUID, workspace_id: str = Query(min_length=1, max_length=120)) -> ApprovalRequestRecord:
    item = policy_approval_service.get_request(request_id, workspace_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return item


@router.post("/requests/{request_id}/cancel", response_model=ApprovalRequestRecord)
def cancel_request(request_id: UUID, payload: PolicyMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ApprovalRequestRecord:
    item = policy_approval_service.cancel_request(request_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Cancellable owned request not found")
    return item


@router.post("/decisions", response_model=ApprovalRequestRecord)
def submit_decision(payload: ApprovalDecisionCreate) -> ApprovalRequestRecord:
    try:
        item = policy_approval_service.decide(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Pending approval request not found")
    return item


@router.get("/decisions", response_model=list[ApprovalDecisionRecord])
def list_decisions(workspace_id: str = Query(min_length=1, max_length=120), request_id: UUID | None = None) -> list[ApprovalDecisionRecord]:
    return policy_approval_service.list_decisions(workspace_id, request_id)


@router.post("/exceptions", response_model=ExceptionRecord, status_code=status.HTTP_201_CREATED)
def create_exception(payload: ExceptionCreate) -> ExceptionRecord:
    try:
        return policy_approval_service.create_exception(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/exceptions", response_model=list[ExceptionRecord])
def list_exceptions(workspace_id: str = Query(min_length=1, max_length=120)) -> list[ExceptionRecord]:
    return policy_approval_service.list_exceptions(workspace_id)


@router.post("/exceptions/{exception_id}/decision", response_model=ExceptionRecord)
def decide_exception(exception_id: UUID, payload: ExceptionDecision, workspace_id: str = Query(min_length=1, max_length=120)) -> ExceptionRecord:
    item = policy_approval_service.decide_exception(exception_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Owned exception request not found")
    return item


@router.post("/exceptions/{exception_id}/revoke", response_model=ExceptionRecord)
def revoke_exception(exception_id: UUID, payload: PolicyMutation, workspace_id: str = Query(min_length=1, max_length=120)) -> ExceptionRecord:
    item = policy_approval_service.revoke_exception(exception_id, workspace_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Revocable owned exception not found")
    return item


@router.get("/audit", response_model=list[AuditRecord])
def list_audit(workspace_id: str = Query(min_length=1, max_length=120)) -> list[AuditRecord]:
    return policy_approval_service.list_audit(workspace_id)
