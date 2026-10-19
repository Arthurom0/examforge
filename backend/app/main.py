import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import app_settings, courses, documents, exercises, generation, tracking
from .services import providers
from .services.extraction import ocr_available

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ExamForge", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (app_settings, courses, documents, exercises, generation, tracking):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "provider": providers.active().id,
        "provider_name": providers.active().name,
        "api_key_configured": providers.active().configured,
        "model": providers.active().model,
        "ocr_available": ocr_available(),
        "ocr_langs": settings.ocr_langs,
    }


# Desktop app: the backend also serves the built frontend (single-page app, so unknown paths get index.html).
if settings.static_dir and Path(settings.static_dir, "index.html").exists():
    _static = Path(settings.static_dir).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        target = (_static / path).resolve()
        if path and target.is_file() and _static in target.parents:
            return FileResponse(target)
        return FileResponse(_static / "index.html")
