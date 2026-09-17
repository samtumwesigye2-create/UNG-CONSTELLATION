from fastapi.testclient import TestClient

from app.web import app


def test_production_root_redirects_to_mission_control():
    client = TestClient(app)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/mission-control"


def test_mission_control_is_html():
    client = TestClient(app)
    response = client.get("/mission-control")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "UNG-CONSTELLATION" in response.text
    assert "Mission Control" in response.text
