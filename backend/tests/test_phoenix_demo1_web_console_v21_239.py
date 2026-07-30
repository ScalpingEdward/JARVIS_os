from fastapi.testclient import TestClient

from app.main import app


def test_v21_239_console_route_is_registered_and_live():
    paths = {route.path for route in app.routes}
    assert '/phoenix/demo1/v21.239/console' in paths

    client = TestClient(app)
    response = client.get('/phoenix/demo1/v21.239/console')
    assert response.status_code == 200
    assert 'text/html' in response.headers['content-type']
    body = response.text
    assert 'PHOENIX' in body
    assert 'Operator Console' in body
    assert '/phoenix/demo1/v21.238/route-and-execute' in body
    assert '/phoenix/demo1/v21.230/dashboard' in body
    assert 'High-risk autonomous execution' in body
