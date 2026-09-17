"""Production ASGI entrypoint for UNG-CONSTELLATION.

Railway launches this module. The core API remains in app.main, while this
entrypoint guarantees that browser requests for / open Mission Control.
"""
from fastapi import Request
from fastapi.responses import RedirectResponse

from .main import app


@app.middleware("http")
async def mission_control_root(request: Request, call_next):
    # Intercept the root before FastAPI route matching. app.main still has a
    # legacy JSON GET / route, so middleware is deliberately used here rather
    # than relying on route-list ordering.
    if request.method in {"GET", "HEAD"} and request.url.path == "/":
        return RedirectResponse(url="/mission-control", status_code=307)
    return await call_next(request)
