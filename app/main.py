from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.documents import router as documents_router
from app.api.review import router as review_router
from app.api.upload import router as upload_router
from app.config import settings
from app.database import Base, engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.ocr_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.extraction_dir).mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/api/review/ui")

    app.include_router(upload_router)
    app.include_router(review_router)
    app.include_router(documents_router)
    return app


app = create_app()
