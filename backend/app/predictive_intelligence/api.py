from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import ForecastRequest, PredictiveReport, PredictiveStatus, WhatIfReport, WhatIfRequest
from .service import predictive_intelligence_service


router = APIRouter(prefix="/v1/predictive-intelligence", tags=["predictive-intelligence"])


@router.get("/status", response_model=PredictiveStatus)
def predictive_status() -> PredictiveStatus:
    return predictive_intelligence_service.status()


@router.post("/reports", response_model=PredictiveReport, status_code=status.HTTP_201_CREATED)
def create_report(payload: ForecastRequest) -> PredictiveReport:
    return predictive_intelligence_service.generate(payload)


@router.get("/reports", response_model=list[PredictiveReport])
def list_reports() -> list[PredictiveReport]:
    return predictive_intelligence_service.list_reports()


@router.get("/reports/{report_id}", response_model=PredictiveReport)
def get_report(report_id: UUID) -> PredictiveReport:
    report = predictive_intelligence_service.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Predictive report not found")
    return report


@router.post("/what-if", response_model=WhatIfReport)
def simulate_what_if(payload: WhatIfRequest) -> WhatIfReport:
    return predictive_intelligence_service.what_if(payload)
