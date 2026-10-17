"""demo_serve.py — demo-only wrapper (NOT in the upstream repo).

Mounts the built frontend (frontend/dist) as StaticFiles at /SpaceHunter
on the same uvicorn :8000 as the FastAPI backend — single origin, no CORS.

Kept in the demo dir (survives VM replacement, unlike the /tmp original).
Run from anywhere:
    ~/workspace/spacehunter-demo/venv/bin/uvicorn demo_serve:app --host 127.0.0.1 --port 8000
"""
import os
import sys

DEMO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(DEMO_DIR, "backend"))

from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402
from app.main import app  # noqa: E402


class SPAStaticFiles(StaticFiles):
    """StaticFiles with an SPA fallback: unknown non-file paths under the
    mount are client-side routes, so serve index.html instead of 404."""

    async def get_response(self, path, scope):
        is_file = "." in path.rsplit("/", 1)[-1]
        try:
            response = await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404 and not is_file:
                return await super().get_response("index.html", scope)
            raise
        if response.status_code == 404 and not is_file:
            return await super().get_response("index.html", scope)
        return response


app.mount(
    "/SpaceHunter",
    SPAStaticFiles(directory=os.path.join(DEMO_DIR, "frontend", "dist"), html=True),
    name="spacehunter",
)
