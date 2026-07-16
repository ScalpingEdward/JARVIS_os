from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .models import AccountSnapshot, AccountSnapshotCreate, PortfolioReport, PortfolioRiskStatus, StressResult, StressScenario
from .service import portfolio_risk_service


router = APIRouter(prefix="/v1/portfolio-risk", tags=["portfolio-risk"])


@router.get("/status", response_model=PortfolioRiskStatus)
def portfolio_risk_status() -> PortfolioRiskStatus:
    return portfolio_risk_service.status()


@router.post("/accounts", response_model=AccountSnapshot, status_code=status.HTTP_201_CREATED)
def add_account_snapshot(payload: AccountSnapshotCreate) -> AccountSnapshot:
    return portfolio_risk_service.add_snapshot(payload)


@router.get("/accounts", response_model=list[AccountSnapshot])
def list_account_snapshots() -> list[AccountSnapshot]:
    return portfolio_risk_service.list_accounts()


@router.get("/accounts/{account_id}", response_model=AccountSnapshot)
def get_account_snapshot(account_id: UUID) -> AccountSnapshot:
    account = portfolio_risk_service.get_account(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Portfolio account snapshot not found")
    return account


@router.get("/report", response_model=PortfolioReport)
def portfolio_report() -> PortfolioReport:
    return portfolio_risk_service.report()


@router.post("/stress", response_model=StressResult)
def run_stress_test(payload: StressScenario) -> StressResult:
    return portfolio_risk_service.stress(payload)
