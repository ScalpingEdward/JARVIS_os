from fastapi import APIRouter,HTTPException,Query
from app.schemas.decision_execution_proposal import ProposalAction,ProposalCreate,ProposalRecord
from app.services.decision_execution_proposal import decision_execution_proposal_service as service
router=APIRouter(prefix="/v1/decision-execution-proposal",tags=["decision-execution-proposal"])
@router.get("/status")
def status(): return service.status()
@router.post("/records",response_model=ProposalRecord)
def create_record(payload:ProposalCreate):
    try:return service.create(payload)
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e
@router.get("/records",response_model=list[ProposalRecord])
def list_records(workspace_id:str=Query(min_length=1)): return service.list(workspace_id)
@router.get("/records/{record_id}",response_model=ProposalRecord)
def get_record(record_id:str,workspace_id:str=Query(min_length=1)):
    try:return service.get(workspace_id,record_id)
    except KeyError as e:raise HTTPException(status_code=404,detail=str(e)) from e
@router.post("/records/{record_id}/actions",response_model=ProposalRecord)
def act(record_id:str,payload:ProposalAction):
    try:return service.act(record_id,payload)
    except KeyError as e:raise HTTPException(status_code=404,detail=str(e)) from e
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e
@router.get("/audit")
def audit(workspace_id:str=Query(min_length=1)): return service.audit(workspace_id)
