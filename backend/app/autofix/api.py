from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.workspace.models import WorkspacePatch

from .models import AutoFixCreate, AutoFixList, AutoFixPatch, AutoFixRecord
from .service import AutoFixError, autofix_service

router = APIRouter(prefix="/v1/autofix", tags=["autofix"])


@router.get("/status")
def status_info() -> dict[str, object]:
    return {
        "bounded_retries": True,
        "maximum_attempts": 5,
        "automatic_merge": False,
        "shell_in_api_process": False,
        "human_escalation": True,
    }


@router.post("/loops", response_model=AutoFixRecord, status_code=status.HTTP_201_CREATED)
def create_loop(payload: AutoFixCreate) -> AutoFixRecord:
    try:
        return autofix_service.create(payload)
    except (AutoFixError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/loops", response_model=AutoFixList)
def list_loops() -> AutoFixList:
    items = autofix_service.list_all()
    return AutoFixList(items=items, count=len(items))


@router.get("/loops/{loop_id}", response_model=AutoFixRecord)
def get_loop(loop_id: UUID) -> AutoFixRecord:
    try:
        return autofix_service.get(loop_id)
    except AutoFixError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/loops/{loop_id}/sandbox/{run_id}", response_model=AutoFixRecord)
def ingest_sandbox_result(loop_id: UUID, run_id: UUID) -> AutoFixRecord:
    try:
        return autofix_service.ingest_sandbox_result(loop_id, run_id)
    except AutoFixError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/loops/{loop_id}/retry", response_model=AutoFixRecord)
def retry_with_patch(loop_id: UUID, patch: WorkspacePatch, attempt: int, summary: str) -> AutoFixRecord:
    try:
        return autofix_service.apply_patch_and_retry(
            loop_id,
            patch,
            AutoFixPatch(attempt=attempt, summary=summary),
        )
    except (AutoFixError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
