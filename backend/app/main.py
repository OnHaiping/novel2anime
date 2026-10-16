from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .api import assets, motions, projects, renders, system
from .config import get_settings
from .database import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.data_root.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_origin, "http://localhost:3300"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(projects.router, prefix="/api")
app.include_router(motions.router, prefix="/api")
app.include_router(renders.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(assets.router, prefix="/api")


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/system/health"}
