from fastapi.testclient import TestClient

from app.main import app


def test_v21_240_console_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.240/console' in paths

    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.240/console')
    assert response.status_code == 200
    assert 'PHOENIX' in response.text
    assert 'Live Result' in response.text
    assert 'Command History' in response.text
    assert '/phoenix/demo1/v21.238/route-and-execute' in response.text
    assert 'High-risk autonomous execution' in response.text
