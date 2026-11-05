"""Research Workspace: dokumentasi etika, anotasi & kesimpulan, bukti, ekspor anonim, audit, retensi."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..cache import bump
from ..db import get_db
from ..deps import client_ip, graph_filters, require
from ..graphs import GraphFilters, content_categories
from ..security import has_permission
from ..services import audit, current_project
from ..sna import DISCLAIMER
from .explorer import _analysis, _annotation_out

router = APIRouter(prefix="/api", tags=["workspace"])


def project_out(p: m.ResearchProject) -> dict:
    return {k: (v.isoformat() if isinstance(v, (date, datetime)) else v) for k, v in {
        "id": p.id, "code": p.code, "name": p.name, "description": p.description, "period_start": p.period_start,
        "period_end": p.period_end, "status": p.status, "is_demo": p.is_demo, "ethics_body": p.ethics_body,
        "ethics_approval_ref": p.ethics_approval_ref, "ethics_approval_date": p.ethics_approval_date, "consent_notes": p.consent_notes,
        "data_minimization_notes": p.data_minimization_notes, "risk_mitigation_notes": p.risk_mitigation_notes,
        "raw_retention_days": p.raw_retention_days, "retention_days": p.retention_days}.items()}


@router.get("/project")
def project(db: Session = Depends(get_db), _=Depends(require("view"))):
    return project_out(current_project(db))


class ProjectPatch(BaseModel):
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    ethics_body: str | None = None
    ethics_approval_ref: str | None = None
    ethics_approval_date: date | None = None
    consent_notes: str | None = None
    data_minimization_notes: str | None = None
    risk_mitigation_notes: str | None = None
    raw_retention_days: int | None = Field(None, ge=1, le=3650)
    retention_days: int | None = Field(None, ge=1, le=3650)


@router.patch("/project")
def update_project(body: ProjectPatch, request: Request, db: Session = Depends(get_db), user=Depends(require("manage_project"))):
    p = current_project(db)
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(p, k, v)
    if p.period_end < p.period_start:
        raise HTTPException(422, "Periode akhir harus setelah periode awal.")
    audit(db, user, "ubah_proyek", "proyek", p.id, {"fields": list(changes)}, client_ip(request))
    db.commit()
    return project_out(p)


@router.get("/annotations")
def annotations(target_type: str | None = None, kind: str | None = None, db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    q = select(m.Annotation).where(m.Annotation.project_id == proj.id)
    if target_type:
        q = q.where(m.Annotation.target_type == target_type)
    if kind:
        q = q.where(m.Annotation.kind == kind)
    users = {u.id: u.display_name for u in db.scalars(select(m.ResearchUser))}
    return [{**_annotation_out(a), "author": users.get(a.author_id), "reviewer": users.get(a.reviewed_by)}
            for a in db.scalars(q.order_by(m.Annotation.id.desc()))]


class AnnotationIn(BaseModel):
    target_type: str = Field(..., pattern="^(konten|aktor|relasi|komunitas|proyek)$")
    target_id: int | None = None
    kind: str = Field("catatan", pattern="^(catatan|kode|kesimpulan)$")
    body: str = Field(..., min_length=3, max_length=5000)
    tags: list[str] = Field(default_factory=list)


@router.post("/annotations")
def create_annotation(body: AnnotationIn, request: Request, db: Session = Depends(get_db), user=Depends(require("annotate"))):
    proj = current_project(db)
    a = m.Annotation(project_id=proj.id, author_id=user.id, review_status="perlu_tinjauan" if body.kind == "kesimpulan" else "draf",
                     **body.model_dump())
    db.add(a)
    db.flush()
    audit(db, user, "buat_anotasi", "anotasi", a.id, {"kind": body.kind}, client_ip(request))
    db.commit()
    return _annotation_out(a)


class AnnotationReview(BaseModel):
    decision: str = Field(..., pattern="^(disetujui|ditolak)$")


@router.post("/annotations/{aid}/review")
def review_annotation(aid: int, body: AnnotationReview, request: Request, db: Session = Depends(get_db),
                      user=Depends(require("approve_conclusion"))):
    a = db.get(m.Annotation, aid)
    if not a:
        raise HTTPException(404, "Anotasi tidak ditemukan.")
    if a.author_id == user.id:
        raise HTTPException(422, "Kesimpulan harus ditinjau oleh peninjau lain (bukan penulis).")
    a.review_status, a.reviewed_by, a.reviewed_at = body.decision, user.id, datetime.now(timezone.utc)
    audit(db, user, "tinjau_kesimpulan", "anotasi", a.id, {"keputusan": body.decision}, client_ip(request))
    db.commit()
    return _annotation_out(a)


@router.get("/evidence")
def evidence(db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    rows = db.scalars(select(m.EvidenceRecord).where(m.EvidenceRecord.project_id == proj.id).order_by(m.EvidenceRecord.id.desc()).limit(300)).all()
    rels = {r.id: r for r in db.scalars(select(m.ContentRelationship).where(m.ContentRelationship.id.in_([e.relationship_id for e in rows if e.relationship_id] or [0])))}
    codes = {c.id: c.code for c in db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id))}
    out = []
    for e in rows:
        r = rels.get(e.relationship_id)
        out.append({"id": e.id, "evidence_type": e.evidence_type, "direction": e.direction, "strength": e.strength,
                    "description": e.description, "created_at": e.created_at.isoformat(),
                    "relationship": {"id": r.id, "source": codes.get(r.source_content_id), "target": codes.get(r.target_content_id),
                                     "evidence_status": r.evidence_status} if r else None,
                    "content": codes.get(e.content_id) if e.content_id else None})
    return out


@router.get("/export/anonymized")
def export_anonymized(request: Request, format: str = "json", include_text: bool = False, f: GraphFilters = Depends(graph_filters),
                      db: Session = Depends(get_db), user=Depends(require("export"))):
    """Ekspor hasil riset anonim: pseudonim, metrik, komunitas, label tervalidasi, kesimpulan yang DISETUJUI.
    Teks hanya untuk peran ber-izin `export_raw`, tidak pernah untuk konten sensitif."""
    proj = current_project(db)
    if include_text and not has_permission(user.role, "export_raw"):
        raise HTTPException(403, "Ekspor teks memerlukan izin 'export_raw'.")
    g, an = _analysis(db, f)
    ccats = content_categories(db, proj.id)
    contents = db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id)).all()
    plats = {p.id: p.code for p in db.scalars(select(m.Platform))}
    validated = {(r.content_id, r.category.code) for r in db.scalars(select(m.ContentClassification)
                                                                     .where(m.ContentClassification.validation_status == "valid"))}
    content_rows, excluded_sensitive = [], 0
    for c in contents:
        if c.is_sensitive:
            excluded_sensitive += 1
            continue
        row = {"code": c.code, "platform": plats[c.platform_id], "actor": c.actor.pseudonym, "published_at_utc": c.published_at.isoformat(),
               "content_type": c.content_type, "context_label": c.context_label,
               "categories": ";".join(ccats.get(c.id, [])),
               "categories_validated": ";".join(code for code in ccats.get(c.id, []) if (c.id, code) in validated)}
        if include_text:
            row["text"] = c.text_excerpt or ""
        content_rows.append(row)
    node_rows = [{"id": n, "label": d.get("label"), "kind": d.get("kind"), "platform": d.get("platform"),
                  "community": an["membership"].get(n), **an["metrics"].get(n, {})} for n, d in g.nodes(data=True)]
    conclusions = [{"body": a.body, "tags": a.tags, "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None}
                   for a in db.scalars(select(m.Annotation).where(m.Annotation.project_id == proj.id, m.Annotation.kind == "kesimpulan",
                                                                  m.Annotation.review_status == "disetujui"))]
    meta = {"project": proj.code, "data_mode": "DEMO" if proj.is_demo else "LIVE", "exported_at": datetime.now(timezone.utc).isoformat(),
            "exported_by_role": user.role, "layer": f.layer, "network_summary": an["summary"], "disclaimer": DISCLAIMER,
            "excluded_sensitive_records": excluded_sensitive, "text_included": include_text,
            "notes": "Pseudonim berbasis HMAC; handle, URL, dan ID platform tidak disertakan. Hanya kesimpulan yang disetujui peninjau kedua."}
    audit(db, user, "ekspor_anonim", "proyek", proj.id, {"format": format, "include_text": include_text, "rows": len(content_rows)},
          client_ip(request))
    db.commit()
    fname = f"laras_ekspor_anonim_{meta['data_mode']}"
    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(content_rows[0].keys()) if content_rows else ["code"])
        w.writeheader()
        w.writerows(content_rows)
        return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{fname}_konten.csv"'})
    body = json.dumps({"meta": meta, "nodes": node_rows, "contents": content_rows, "communities": an["communities"],
                       "approved_conclusions": conclusions}, ensure_ascii=False, indent=1)
    return Response(body, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{fname}.json"'})


@router.get("/audit")
def audit_log(limit: int = 200, db: Session = Depends(get_db), _=Depends(require("view_audit"))):
    return [{"id": a.id, "username": a.username, "action": a.action, "resource_type": a.resource_type, "resource_id": a.resource_id,
             "details": a.details, "ip_address": a.ip_address, "created_at": a.created_at.isoformat()}
            for a in db.scalars(select(m.AuditLog).order_by(m.AuditLog.id.desc()).limit(min(limit, 1000)))]


@router.post("/retention/apply")
def apply_retention(request: Request, dry_run: bool = True, db: Session = Depends(get_db), user=Depends(require("manage_project"))):
    """Hapus teks mentah yang melewati masa retensi mentah (data terolah tetap)."""
    proj = current_project(db)
    cutoff = datetime.now(timezone.utc) - timedelta(days=proj.raw_retention_days)
    items = db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id, m.ContentItem.collected_at < cutoff,
                                                   m.ContentItem.text_excerpt.is_not(None))).all()
    if not dry_run:
        now = datetime.now(timezone.utc)
        for c in items:
            c.text_excerpt, c.text_normalized, c.raw_purged_at = None, None, now
        audit(db, user, "terapkan_retensi", "proyek", proj.id, {"purged": len(items), "cutoff": cutoff.isoformat()}, client_ip(request))
        db.commit()
        bump()
    return {"dry_run": dry_run, "cutoff": cutoff.isoformat(), "affected": len(items)}
