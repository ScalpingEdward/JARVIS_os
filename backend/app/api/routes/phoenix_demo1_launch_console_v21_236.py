from fastapi import APIRouter

from app.schemas.phoenix_demo1_launch_console_v21_236 import LaunchConsoleRequest, LaunchConsoleResult
from app.services.phoenix_demo1_launch_console_v21_236 import build_launch_console

router = APIRouter(prefix='/phoenix/demo1/v21.236', tags=['phoenix-demo1-launch'])


@router.post('/launch-console', response_model=LaunchConsoleResult)
def launch_console(payload: LaunchConsoleRequest) -> LaunchConsoleResult:
    return build_launch_console(payload)
