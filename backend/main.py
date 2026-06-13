"""main.py — FastAPI app entrypoint for the GitInsight prototype read API.

Run: uv run uvicorn main:app --reload   (from backend/)

All routes live under /api/v1/. Data access is RLS-enforced via org_session() inside the
endpoints; this module only wires the app and manages the asyncpg pools' lifecycle.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.v1 import router as v1_router
from db.session import close_pools


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_pools()


app = FastAPI(title="GitInsight API", version="0.1.0", lifespan=lifespan)
app.include_router(v1_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
