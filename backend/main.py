import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .core.config import get_settings
from .core.logging import logger
from .api.routes import router
from .rag.store import get_vector_store

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting FinOps Agent — model: {settings.ollama_model} | env: {settings.app_env}")
    store = get_vector_store()
    try:
        await store.initialize()
        logger.info("Vector store ready")
    except Exception as e:
        logger.warning(f"Vector store init failed (will retry on first request): {e}")
    yield
    logger.info("FinOps Agent shutting down")


app = FastAPI(
    title="FinOps Advisory Agent",
    description="Cloud Cost Anomaly Detection & Advisory Agent — LangGraph + Qdrant + Ollama",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        return FileResponse(os.path.join(frontend_dist, "index.html"))
