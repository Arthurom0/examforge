import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import courses, documents, exercises, generation, tracking
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

for r in (courses, documents, exercises, generation, tracking):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "api_key_configured": settings.has_api_key,
        "model": settings.anthropic_model,
        "ocr_available": ocr_available(),
        "ocr_langs": settings.ocr_langs,
    }
