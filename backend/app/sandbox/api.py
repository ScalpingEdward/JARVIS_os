from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from .models import SandboxResultIn, SandboxRunCreate, SandboxRunList, SandboxRunRecord
from .service import SandboxError, sandbox_service

router = APIRouter(prefix="/v1/sandbox", tags=["sandbox"])


class SandboxStatusResponse(BaseModel):
    execution_location: str
    shell_in_api_process: bool
    network_default: bool
    privileged_containers: bool
    allowed_images: list[str]


@router.get("/status", response_model=SandboxStatusResponse)
def status_info() -> SandboxStatusResponse:
    return SandboxStatusResponse(
        execution_location="external_isolated_runner",
        shell_in_api_process=False,
        network_default=False,
        privileged_containers=False,
        allowed_images=sorted(str(image) for image in sandbox_service.ALLOWED_IMAGES),
    )


@router.post("/runs", response_model=SandboxRunRecord, status_code=status.HTTP_201_CREATED)
def create_run(payload: SandboxRunCreate) -> SandboxRunRecord:
    try:
        return sandbox_service.create(payload)
    except (SandboxError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs", response_model=SandboxRunList)
def list_runs() -> SandboxRunList:
    items = sandbox_service.list_all()
    return SandboxRunList(items=items, count=len(items))


@router.post("/worker/claim-next", response_model=SandboxRunRecord, responses={204: {"description": "No queued job"}})
def claim_next_run() -> SandboxRunRecord | Response:
    run = sandbox_service.claim_next()
    if run is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return run


@router.get("/runs/{run_id}", response_model=SandboxRunRecord)
def get_run(run_id: UUID) -> SandboxRunRecord:
    try:
        return sandbox_service.get(run_id)
    except SandboxError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/runs/{run_id}/claim", response_model=SandboxRunRecord)
def claim_run(run_id: UUID) -> SandboxRunRecord:
    try:
        return sandbox_service.claim(run_id)
    except SandboxError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/runs/{run_id}/complete", response_model=SandboxRunRecord)
def complete_run(run_id: UUID, payload: SandboxResultIn) -> SandboxRunRecord:
    try:
        return sandbox_service.complete(run_id, payload)
    except SandboxError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
