"""Data Collection: konektor, sumber data, job pengumpulan, impor CSV/JSON."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..cache import bump
from ..config import settings
from ..connectors import REGISTRY, get_connector
from ..db import SessionLocal, get_db
from ..deps import client_ip, require
from ..ingest import IMPORT_TEMPLATE_FIELDS, ingest_items, parse_import_file, run_job
from ..services import audit, current_project

router = APIRouter(prefix="/api", tags=["collection"])


@router.get("/connectors")
def connectors(_=Depends(require("view"))):
    return [cls().describe() for cls in REGISTRY.values()]


def source_out(s: m.DataSource) -> dict:
    return {"id": s.id, "name": s.name, "platform": s.platform.code, "source_type": s.source_type, "connector_key": s.connector_key,
            "legal_basis": s.legal_basis, "access_level": s.access_level, "credential_env": s.credential_env,
            "authorization_status": s.authorization_status,
            "authorization_checked_at": s.authorization_checked_at.isoformat() if s.authorization_checked_at else None,
            "quota_daily": s.quota_daily, "quota_used_today": s.quota_used_today}


@router.get("/sources")
def sources(db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    return [source_out(s) for s in db.scalars(select(m.DataSource).where(m.DataSource.project_id == proj.id).order_by(m.DataSource.id))]


class SourcePatch(BaseModel):
    legal_basis: str | None = Field(None, min_length=10, max_length=4000)
    access_level: str | None = Field(None, pattern="^(publik_agregat|terbatas|sensitif)$")
    quota_daily: int | None = Field(None, ge=0)


@router.patch("/sources/{source_id}")
def update_source(source_id: int, body: SourcePatch, request: Request, db: Session = Depends(get_db), user=Depends(require("manage_sources"))):
    s = db.get(m.DataSource, source_id)
    if not s:
        raise HTTPException(404, "Sumber tidak ditemukan.")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(s, k, v)
    audit(db, user, "ubah_sumber", "sumber", s.id, body.model_dump(exclude_none=True), client_ip(request))
    db.commit()
    return source_out(s)


@router.post("/sources/{source_id}/check")
def check_source(source_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require("manage_sources"))):
    s = db.get(m.DataSource, source_id)
    if not s:
        raise HTTPException(404, "Sumber tidak ditemukan.")
    if s.source_type == "demo":
        return source_out(s)
    from datetime import datetime, timezone
    status = get_connector(s.connector_key).check_authorization()
    s.authorization_status, s.authorization_checked_at = status.status, datetime.now(timezone.utc)
    audit(db, user, "cek_otorisasi", "sumber", s.id, {"status": status.status}, client_ip(request))
    db.commit()
    return {**source_out(s), "message": status.message}


def job_out(j: m.CollectionJob) -> dict:
    return {"id": j.id, "source": j.source.name, "source_id": j.source_id, "connector_key": j.source.connector_key, "status": j.status,
            "query": j.query, "params": j.params, "created_at": j.created_at.isoformat(),
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None, "items_fetched": j.items_fetched,
            "items_new": j.items_new, "items_duplicate": j.items_duplicate, "items_rejected": j.items_rejected,
            "quota_used": j.quota_used, "error_log": j.error_log}


@router.get("/jobs")
def jobs(db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    return [job_out(j) for j in db.scalars(select(m.CollectionJob).where(m.CollectionJob.project_id == proj.id)
                                           .order_by(m.CollectionJob.id.desc()).limit(100))]


class JobIn(BaseModel):
    source_id: int
    query: str = Field(..., min_length=2, max_length=1000)
    params: dict = Field(default_factory=dict)


def _run_in_background(job_id: int) -> None:
    with SessionLocal() as db:
        run_job(db, job_id)
    bump()


@router.post("/jobs")
def create_job(body: JobIn, background: BackgroundTasks, request: Request, db: Session = Depends(get_db), user=Depends(require("run_jobs"))):
    proj = current_project(db)
    s = db.get(m.DataSource, body.source_id)
    if not s or s.project_id != proj.id:
        raise HTTPException(404, "Sumber tidak ditemukan.")
    if s.source_type != "api":
        raise HTTPException(422, "Job hanya untuk sumber API. Gunakan Impor untuk berkas.")
    connector = REGISTRY[s.connector_key]
    if connector.availability == "placeholder":
        raise HTTPException(422, connector.notes)
    j = m.CollectionJob(project_id=proj.id, source_id=s.id, query=body.query, params=body.params, requested_by=user.id, status="antri")
    db.add(j)
    db.flush()
    audit(db, user, "buat_job", "collection_job", j.id, {"source": s.name}, client_ip(request))
    db.commit()
    if settings.worker_mode == "inline":
        background.add_task(_run_in_background, j.id)
    return job_out(j)


@router.get("/import/template")
def import_template(_=Depends(require("view"))):
    sample = ("platform,external_id,author_handle,published_at,text,content_type,parent_external_id,parent_author_handle,"
              "interaction_type,views,likes,comments,shares,has_media\n"
              "x,1001,akun_contoh_a,2026-07-14T19:20:00+07:00,contoh posting publik,posting,,,,0,12,3,1,false\n"
              "x,1002,akun_contoh_b,2026-07-14T21:05:00+07:00,contoh balasan,balasan,1001,akun_contoh_a,balasan,0,2,0,0,false\n")
    return Response(sample, media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="templat_impor_laras.csv"'})


@router.get("/import/schema")
def import_schema(_=Depends(require("view"))):
    return {"fields": IMPORT_TEMPLATE_FIELDS, "required": IMPORT_TEMPLATE_FIELDS[:5],
            "notes": ["published_at: ISO-8601 (zona waktu dipertahankan lalu dinormalkan ke UTC) atau epoch detik; tanpa zona dianggap UTC.",
                      "author_handle hanya dipakai untuk membuat pseudonim (HMAC) lalu dibuang — tidak disimpan.",
                      "Duplikat (platform + external_id) dilewati, baik di dalam berkas maupun terhadap basis data.",
                      "Relasi & interaksi dibuat hanya bila parent_external_id terdokumentasi pada data sumber."]}


@router.post("/import")
async def import_file(request: Request, file: UploadFile = File(...), source_id: int = Form(...), legal_basis: str = Form(...),
                      dry_run: bool = Form(True), default_platform: str | None = Form(None), db: Session = Depends(get_db),
                      user=Depends(require("import"))):
    proj = current_project(db)
    s = db.get(m.DataSource, source_id)
    if not s or s.project_id != proj.id:
        raise HTTPException(404, "Sumber tidak ditemukan.")
    if len(legal_basis.strip()) < 10:
        raise HTTPException(422, "Dasar hukum/izin akses wajib dijelaskan (min. 10 karakter).")
    raw = await file.read()
    if len(raw) > settings.max_import_bytes:
        raise HTTPException(413, f"Berkas melebihi batas {settings.max_import_bytes // 1024 // 1024} MB.")
    try:
        report = parse_import_file(file.filename or "", raw, default_platform)
    except (ValueError, UnicodeDecodeError, KeyError) as e:
        raise HTTPException(422, f"Berkas tidak dapat dibaca: {e}")
    out = {"dry_run": dry_run, "validation": report.as_dict()}
    if not dry_run and report.valid:
        job = m.CollectionJob(project_id=proj.id, source_id=s.id, status="berjalan", query=f"impor:{file.filename}",
                              params={"legal_basis": legal_basis[:500]}, requested_by=user.id)
        db.add(job)
        db.flush()
        stats = ingest_items(db, proj, s, report.valid, job)
        job.status = "selesai"
        job.items_fetched, job.items_new, job.items_duplicate = stats.fetched, stats.new, stats.duplicate + report.duplicates_in_file
        job.items_rejected = len({e["row"] for e in report.errors}) + stats.rejected
        job.error_log = [{"level": "validasi", **e} for e in report.errors[:100]] + stats.errors
        job.started_at = job.finished_at = job.created_at
        audit(db, user, "impor_berkas", "collection_job", job.id, {"file": file.filename, "new": stats.new, "dup": stats.duplicate},
              client_ip(request))
        db.commit()
        bump()
        out["result"] = {"job_id": job.id, "new": stats.new, "duplicate": stats.duplicate, "relations": stats.relations,
                         "interactions": stats.interactions}
    return out
