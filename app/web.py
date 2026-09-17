"""Production ASGI entrypoint for UNG-CONSTELLATION.

The API implementation remains in app.main.  This entrypoint makes the public
root URL behave like an application URL instead of exposing the service JSON
manifest to browser users.
"""
from fastapi.responses import RedirectResponse

from .main import app

# app.main historically exposes GET / as a JSON service manifest. Keep the API
# available under /v1/system and make the browser-facing production root open
# Mission Control instead.
app.router.routes[:] = [
    route
    for route in app.router.routes
    if not (
        getattr(route, "path", None) == "/"
        and "GET" in (getattr(route, "methods", None) or set())
    )
]


@app.get("/", include_in_schema=False)
def constellation_ui_root():
    return RedirectResponse(url="/mission-control", status_code=307)
