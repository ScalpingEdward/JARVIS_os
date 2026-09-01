from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.modules.dynamic_risk_engine.models import DynamicRiskRecord
from app.modules.execution_supervisor.models import SupervisionRecord
from app.modules.position_management_brain.models import PositionRecord

from .models import RiskAssessmentRequest, SupervisionStartRequest
from .service import TradeRiskPipelineError, trade_risk_pipeline_service

router = APIRouter(prefix="/v1/trade-risk-pipeline", tags=["trade-risk-pipeline"])


@router.post("/assess/{approval_request_id}", response_model=DynamicRiskRecord)
def assess(approval_request_id: UUID, request: RiskAssessmentRequest = RiskAssessmentRequest()) -> DynamicRiskRecord:
    """Runs a real, policy-bounded risk assessment for an already-approved setup.

    Pulls the setup from setup_submission's approval queue and the account's
    live state from the account registry -- nothing here re-specifies the
    trade. Returns the dynamic_risk_engine record (risk-approved, human-
    review-required, or blocked) with the actual recommended position size.
    Does not open a position or place an order.
    """
    try:
        return trade_risk_pipeline_service.assess(approval_request_id, request)
    except TradeRiskPipelineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/accounts/{workspace_id}/open-position/{risk_record_id}", response_model=PositionRecord)
def open_position(workspace_id: str, risk_record_id: str) -> PositionRecord:
    """Opens a tracked position from an already risk-approved assessment.

    Requires the risk record returned by /assess to be in the risk-approved
    state. Maps the strategy's take-profits into real exit rules in
    position_management_brain. Still does not place a broker order.
    """
    try:
        return trade_risk_pipeline_service.open_position(workspace_id, risk_record_id)
    except TradeRiskPipelineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/accounts/{workspace_id}/positions/{position_id}/start-supervision", response_model=SupervisionRecord)
def start_supervision(
    workspace_id: str, position_id: str, request: SupervisionStartRequest = SupervisionStartRequest()
) -> SupervisionRecord:
    """Starts execution_supervisor health tracking for an already-opened position.

    Requires the position to be in an open/planned/approved/protected/
    scaling-out state. Refuses closed, blocked, invalidated, or archived
    positions.
    """
    try:
        return trade_risk_pipeline_service.start_supervision(workspace_id, position_id, request)
    except TradeRiskPipelineError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
