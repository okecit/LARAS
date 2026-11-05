"""LARAs / YOUTH-SNA — API riset (FastAPI)."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import analytics, auth, collection, content, diffusion, explorer, workspace

log = logging.getLogger("laras")

app = FastAPI(title="LARAs — YOUTH-SNA API", version="0.1.0",
              description="Youth Social Behavior Network Analytics. Semua teks antarmuka berbahasa Indonesia.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth, explorer, analytics, content, diffusion, collection, workspace):
    app.include_router(r.router)


@app.on_event("startup")
def _warn_dev_secret() -> None:
    if settings.is_dev_secret:
        log.warning("YSNA_JWT_SECRET memakai nilai pengembangan. Ganti sebelum dipakai dengan data nyata.")


@app.get("/api/health")
def health():
    return {"status": "ok", "data_mode": settings.data_mode, "worker_mode": settings.worker_mode}
