from fastapi import APIRouter

from .service import backup_service

router = APIRouter(prefix="/v1/backup", tags=["backup"])


@router.post("/status")
def report(status: dict) -> dict:
    """tools/backup.py reports every run here."""
    return backup_service.report(status)


@router.get("/status")
def status() -> dict:
    return backup_service.view()
