from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.auron_demo1_telegram_successor_next_generation_forty_four_restoration_v21_515 import command_center, router, status


def client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_routes_registered() -> None:
    paths = {route.path for route in router.routes}
    assert '/auron/demo1/v21.515/restoration/prepare' in paths
    assert '/auron/demo1/v21.515/activation/execute' in paths
    assert '/auron/demo1/v21.515/succession/certify' in paths
    assert '/auron/demo1/v21.515/status' in paths
    assert '/auron/demo1/v21.515/command-center' in paths


def test_safe_empty_status() -> None:
    result = status()
    assert result['external_calls_made'] == 0
    assert result['mode'] == 'successor-next-generation-forty-four-restoration-activation-succession'


def test_command_center_safety() -> None:
    html = command_center()
    assert 'AURON v21.515' in html
    assert 'no Telegram API call' in html
    assert 'external_calls_made=0' in html
