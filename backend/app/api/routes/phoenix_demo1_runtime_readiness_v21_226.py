from fastapi import APIRouter
from app.schemas.phoenix_demo1_runtime_readiness_v21_226 import DemoRuntimeReadiness
from app.services.phoenix_demo1_runtime_readiness_v21_226 import runtime_readiness

router = APIRouter(prefix='/phoenix/demo1/v21.226', tags=['phoenix-demo1-v21.226'])


@router.get('/readiness', response_model=DemoRuntimeReadiness)
def readiness():
    return runtime_readiness()
