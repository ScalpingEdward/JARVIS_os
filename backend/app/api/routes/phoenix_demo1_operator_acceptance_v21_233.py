from fastapi import APIRouter

from app.schemas.phoenix_demo1_operator_acceptance_v21_233 import OperatorAcceptanceRequest, OperatorAcceptanceResult
from app.services.phoenix_demo1_operator_acceptance_v21_233 import build_operator_acceptance

router = APIRouter(prefix='/phoenix/demo1/v21.233', tags=['phoenix-demo1-v21.233'])


@router.post('/acceptance', response_model=OperatorAcceptanceResult)
def operator_acceptance(req: OperatorAcceptanceRequest):
    return build_operator_acceptance(req)
