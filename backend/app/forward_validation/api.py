from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ForwardValidationStatus, ValidationCreate, ValidationReport
from .service import forward_validation_service


router = APIRouter(prefix="/v1/forward-validation", tags=["forward-validation"])


@router.get("/status", response_model=ForwardValidationStatus)
def validation_status() -> ForwardValidationStatus:
    return forward_validation_service.status()


@router.post("/reports", response_model=ValidationReport, status_code=status.HTTP_201_CREATED)
def create_report(payload: ValidationCreate) -> ValidationReport:
    return forward_validation_service.create(payload)


@router.get("/reports", response_model=list[ValidationReport])
def list_reports() -> list[ValidationReport]:
    return forward_validation_service.list_all()


@router.get("/reports/{report_id}", response_model=ValidationReport)
def get_report(report_id: UUID) -> ValidationReport:
    report = forward_validation_service.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Forward validation report not found")
    return report
