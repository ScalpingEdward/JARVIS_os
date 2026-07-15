import os
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .models import WorkflowCreate, WorkflowListResponse, WorkflowRecord, WorkflowTickResponse
from .scheduler import workflow_scheduler
from .service import ExecutionError, autonomous_execution_service

router = APIRouter(prefix="/v1/execution", tags=["execution"])
_ui_dir = Path(__file__).resolve().parent.parent / "ui"
_ui_assets = {
    "app.js": "application/javascript",
    "voice.js": "application/javascript",
    "styles.css": "text/css",
}


@router.on_event("startup")
def start_configured_scheduler() -> None:
    if os.getenv("JARVIS_SCHEDULER_ENABLED", "false").lower() in {"1", "true", "yes"}:
        workflow_scheduler.start()


@router.on_event("shutdown")
def stop_configured_scheduler() -> None:
    workflow_scheduler.stop()


def _call(operation):
    try:
        return operation()
    except ExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/control-center", include_in_schema=False)
def control_center() -> FileResponse:
    return FileResponse(_ui_dir / "index.html", media_type="text/html")


@router.get("/mobile-voice", include_in_schema=False)
def mobile_voice() -> FileResponse:
    return FileResponse(_ui_dir / "voice.html", media_type="text/html")


@router.get("/control-center/assets/{asset_name}", include_in_schema=False)
def control_center_asset(asset_name: str) -> FileResponse:
    media_type = _ui_assets.get(asset_name)
    if media_type is None:
        raise HTTPException(status_code=404, detail="UI asset not found")
    return FileResponse(_ui_dir / asset_name, media_type=media_type)


@router.post("/workflows", response_model=WorkflowRecord)
def create_workflow(payload: WorkflowCreate) -> WorkflowRecord:
    return autonomous_execution_service.create(payload)


@router.get("/workflows", response_model=WorkflowListResponse)
def list_workflows() -> WorkflowListResponse:
    items = autonomous_execution_service.list_workflows()
    return WorkflowListResponse(items=items, count=len(items))


@router.get("/workflows/{workflow_id}", response_model=WorkflowRecord)
def get_workflow(workflow_id: UUID) -> WorkflowRecord:
    return _call(lambda: autonomous_execution_service.get(workflow_id))


@router.post("/workflows/{workflow_id}/start", response_model=WorkflowRecord)
def start_workflow(workflow_id: UUID) -> WorkflowRecord:
    return _call(lambda: autonomous_execution_service.start(workflow_id))


@router.post("/workflows/{workflow_id}/pause", response_model=WorkflowRecord)
def pause_workflow(workflow_id: UUID) -> WorkflowRecord:
    return _call(lambda: autonomous_execution_service.pause(workflow_id))


@router.post("/workflows/{workflow_id}/cancel", response_model=WorkflowRecord)
def cancel_workflow(workflow_id: UUID) -> WorkflowRecord:
    return _call(lambda: autonomous_execution_service.cancel(workflow_id))


@router.post("/workflows/{workflow_id}/tick", response_model=WorkflowTickResponse)
def tick_workflow(workflow_id: UUID) -> WorkflowTickResponse:
    return _call(lambda: autonomous_execution_service.tick(workflow_id))


@router.post(
    "/workflows/{workflow_id}/steps/{step_id}/approve",
    response_model=WorkflowRecord,
)
def approve_step(workflow_id: UUID, step_id: UUID) -> WorkflowRecord:
    return _call(lambda: autonomous_execution_service.approve_step(workflow_id, step_id))


@router.get("/scheduler/status")
def scheduler_status() -> dict[str, object]:
    return workflow_scheduler.status()


@router.post("/scheduler/start")
def scheduler_start() -> dict[str, object]:
    workflow_scheduler.start()
    return workflow_scheduler.status()


@router.post("/scheduler/stop")
def scheduler_stop() -> dict[str, object]:
    workflow_scheduler.stop()
    return workflow_scheduler.status()


@router.post("/scheduler/run-once")
def scheduler_run_once() -> dict[str, object]:
    processed = workflow_scheduler.run_once()
    return {**workflow_scheduler.status(), "processed_workflows": processed}
