from fastapi import APIRouter
from app.schemas.phoenix_demo1_v21_225 import DemoRequest, DemoResponse, DemoStatus
from app.services.phoenix_demo1_v21_225 import run_demo_vertical_slice, demo_status

router = APIRouter(prefix='/phoenix/demo1/v21.225', tags=['phoenix-demo1-v21.225'])

@router.get('/status', response_model=DemoStatus)
def status():
    return demo_status()

@router.post('/run', response_model=DemoResponse)
def run(req: DemoRequest):
    return run_demo_vertical_slice(req)
