"""GEOlogic app: FastAPI API plus the built React frontend (StoreSight IQ pattern)."""
import os
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src"))          # bundled copy of src/geologic (deployed app)
sys.path.insert(0, os.path.join(HERE, "..", "src"))    # repo layout (local runs and tests)
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from backend.routes import router

app = FastAPI(title="GEOlogic")
app.include_router(router, prefix="/api")
DIST = os.path.join(HERE, "frontend", "dist")
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = os.path.join(DIST, path)
        return FileResponse(f if path and os.path.isfile(f) else os.path.join(DIST, "index.html"))
