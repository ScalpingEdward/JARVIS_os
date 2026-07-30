from fastapi import APIRouter

from app.schemas.phoenix_demo1_operator_dashboard_v21_230 import OperatorDashboardRequest, OperatorDashboardSnapshot
from app.services.phoenix_demo1_operator_dashboard_v21_230 import build_operator_dashboard

router = APIRouter(prefix='/phoenix/demo1/v21.230', tags=['phoenix-demo1-v21.230'])


@router.post('/dashboard', response_model=OperatorDashboardSnapshot)
def dashboard(req: OperatorDashboardRequest):
    return build_operator_dashboard(req)
