from fastapi import APIRouter

from app.schemas.phoenix_demo1_integration_validation_v21_232 import DemoScenarioRequest, DemoScenarioResult
from app.services.phoenix_demo1_integration_validation_v21_232 import run_demo_scenario

router = APIRouter(prefix='/phoenix/demo1/v21.232', tags=['phoenix-demo1-v21.232'])


@router.post('/validate', response_model=DemoScenarioResult)
def validate_demo1(req: DemoScenarioRequest):
    return run_demo_scenario(req)
