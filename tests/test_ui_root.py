from app.web import app


def _route(path: str, method: str = "GET"):
    return next(
        route
        for route in app.router.routes
        if getattr(route, "path", None) == path
        and method in (getattr(route, "methods", None) or set())
    )


def test_production_root_redirects_to_mission_control():
    response = _route("/").endpoint()
    assert response.status_code == 307
    assert response.headers["location"] == "/mission-control"


def test_mission_control_ui_is_present():
    html = _route("/mission-control").endpoint()
    assert "UNG-CONSTELLATION" in html
    assert "Mission Control" in html
    assert "Satellite Tracking" in html
