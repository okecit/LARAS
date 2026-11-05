"""Content Intelligence: taksonomi, klasifikasi, tinjauan manusia, penemuan kata kunci, kemiripan."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..cache import bump
from ..classifier import RuleClassifier, discover_keywords
from ..db import get_db
from ..deps import client_ip, require
from ..security import has_permission
from ..services import audit, category_dicts, classify_contents, current_project, mask_text
from ..textproc import similarity

router = APIRouter(prefix="/api", tags=["content"])


def category_out(c: m.ContentCategory) -> dict:
    return {"id": c.id, "code": c.code, "name": c.name_id, "name_en": c.name_en, "definition": c.definition,
            "inclusion_criteria": c.inclusion_criteria, "exclusion_criteria": c.exclusion_criteria, "keywords": c.keywords,
            "context_rules": c.context_rules, "min_confidence": c.min_confidence, "color": c.color, "version": c.version,
            "is_active": c.is_active, "updated_at": c.updated_at.isoformat()}


@router.get("/categories")
def categories(db: Session = Depends(get_db), _=Depends(require("view"))):
    return [category_out(c) for c in db.scalars(select(m.ContentCategory).order_by(m.ContentCategory.code))]


class CategoryPatch(BaseModel):
    definition: str | None = None
    inclusion_criteria: list[str] | None = None
    exclusion_criteria: list[str] | None = None
    keywords: list[dict[str, Any]] | None = None
    min_confidence: float | None = Field(None, ge=0, le=1)
    is_active: bool | None = None


@router.patch("/categories/{code}")
def update_category(code: str, body: CategoryPatch, request: Request, db: Session = Depends(get_db),
                    user=Depends(require("edit_taxonomy"))):
    c = db.scalars(select(m.ContentCategory).where(m.ContentCategory.code == code)).first()
    if not c:
        raise HTTPException(404, "Kategori tidak ditemukan.")
    changes = body.model_dump(exclude_none=True)
    if "keywords" in changes:
        clean = []
        for kw in changes["keywords"]:
            term = str(kw.get("term", "")).strip().lower()
            if term:
                clean.append({"term": term[:60], "weight": max(0.1, min(2.0, float(kw.get("weight", 1.0))))})
        changes["keywords"] = clean
    for k, v in changes.items():
        setattr(c, k, v)
    c.version += 1
    audit(db, user, "ubah_taksonomi", "kategori", code, {"fields": list(changes), "version": c.version}, client_ip(request))
    db.commit()
    return category_out(c)


class ClassifyIn(BaseModel):
    text: str = Field(..., max_length=5000)


@router.post("/classify/test")
def classify_test(body: ClassifyIn, db: Session = Depends(get_db), _=Depends(require("view"))):
    res = RuleClassifier(category_dicts(db)).classify(body.text)
    return {"normalized_text": res.normalized_text, "context_label": res.context_label, "context_markers": res.context_markers,
            "model_version": res.model_version,
            "labels": [{"code": l.code, "confidence": l.confidence, "matched_terms": l.matched_terms, "context_label": l.context_label,
                        "rationale": l.rationale} for l in res.labels],
            "note": "Hasil uji tidak disimpan. Label mesin bukan keputusan akhir dan tidak menilai penulis."}


@router.post("/classify/run")
def classify_run(request: Request, db: Session = Depends(get_db), user=Depends(require("edit_taxonomy"))):
    proj = current_project(db)
    items = db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id)).all()
    n = classify_contents(db, items)
    audit(db, user, "klasifikasi_ulang", "proyek", proj.id, {"labels": n}, client_ip(request))
    db.commit()
    bump()
    return {"items": len(items), "labels": n}


@router.get("/classifications")
def classification_queue(status: str = "belum_ditinjau", category: str | None = None, context: str | None = None,
                         limit: int = 50, offset: int = 0, db: Session = Depends(get_db), user=Depends(require("view"))):
    proj = current_project(db)
    can_raw = has_permission(user.role, "view_raw")
    q = (select(m.ContentClassification).join(m.ContentItem).join(m.ContentCategory)
         .where(m.ContentItem.project_id == proj.id))
    if status != "semua":
        q = q.where(m.ContentClassification.validation_status == status)
    if category:
        q = q.where(m.ContentCategory.code == category)
    if context:
        q = q.where(m.ContentClassification.context_label == context)
    total = len(db.scalars(q).all())
    rows = db.scalars(q.order_by(m.ContentClassification.confidence.desc(), m.ContentClassification.id).offset(offset).limit(limit)).all()
    return {"total": total, "items": [{
        "id": r.id, "content_id": f"c{r.content_id}", "content_code": r.content.code, "platform": r.content.platform.code,
        "published_at": r.content.published_at.isoformat(), "text": mask_text(r.content.text_excerpt, can_raw),
        "category": r.category.code, "category_name": r.category.name_id, "confidence": r.confidence, "method": r.method,
        "model_version": r.model_version, "matched_terms": r.matched_terms, "context_label": r.context_label,
        "rationale": r.rationale, "validation_status": r.validation_status, "reviewer_note": r.reviewer_note,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None} for r in rows]}


class ReviewIn(BaseModel):
    decision: str = Field(..., pattern="^(valid|ditolak|direvisi)$")
    note: str | None = None
    context_label: str | None = None


@router.post("/classifications/{cid}/review")
def review(cid: int, body: ReviewIn, request: Request, db: Session = Depends(get_db), user=Depends(require("validate"))):
    r = db.get(m.ContentClassification, cid)
    if not r:
        raise HTTPException(404, "Klasifikasi tidak ditemukan.")
    before = r.validation_status
    r.validation_status, r.reviewer_note = body.decision, body.note
    r.reviewer_id, r.reviewed_at = user.id, datetime.now(timezone.utc)
    if body.context_label:
        r.context_label = body.context_label
        r.content.context_label = body.context_label
    audit(db, user, "tinjau_klasifikasi", "klasifikasi", cid, {"dari": before, "ke": body.decision}, client_ip(request))
    db.commit()
    bump()
    return {"id": r.id, "validation_status": r.validation_status}


@router.get("/keywords/discover")
def keyword_discovery(db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    cats = db.scalars(select(m.ContentCategory)).all()
    rows = db.execute(select(m.ContentCategory.code, m.ContentItem.text_excerpt)
                      .join(m.ContentClassification, m.ContentClassification.category_id == m.ContentCategory.id)
                      .join(m.ContentItem, m.ContentItem.id == m.ContentClassification.content_id)
                      .where(m.ContentItem.project_id == proj.id, m.ContentClassification.validation_status != "ditolak",
                             m.ContentClassification.context_label == "kandidat_berbahaya")).all()
    by_cat: dict[str, list[str]] = {c.code: [] for c in cats}
    for code, txt in rows:
        if txt:
            by_cat[code].append(txt)
    all_texts = [t for t in db.scalars(select(m.ContentItem.text_excerpt).where(m.ContentItem.project_id == proj.id)) if t]
    existing = {c.code: {k["term"] for k in c.keywords} for c in cats}
    return {"suggestions": discover_keywords(by_cat, all_texts, existing),
            "note": "Usulan otomatis berstatus 'usulan'. Tambahkan ke kamus hanya setelah ditinjau peneliti."}


@router.get("/content/{content_id}/similar")
def similar(content_id: int, threshold: float = 0.45, limit: int = 15, db: Session = Depends(get_db), user=Depends(require("view"))):
    proj = current_project(db)
    base = db.get(m.ContentItem, content_id)
    if not base or not base.text_excerpt:
        raise HTTPException(404, "Konten tidak ditemukan atau teks sudah dihapus.")
    can_raw = has_permission(user.role, "view_raw")
    out = []
    for c in db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id, m.ContentItem.id != base.id)):
        if not c.text_excerpt:
            continue
        s = similarity(base.text_excerpt, c.text_excerpt)
        if s >= threshold:
            out.append({"id": f"c{c.id}", "db_id": c.id, "code": c.code, "platform": c.platform.code, "similarity": s,
                        "published_at": c.published_at.isoformat(), "after_base": c.published_at > base.published_at,
                        "same_actor": c.actor_id == base.actor_id, "text": mask_text(c.text_excerpt, can_raw)})
    out.sort(key=lambda x: -x["similarity"])
    return {"base": {"id": f"c{base.id}", "code": base.code}, "candidates": out[:limit],
            "note": "Kemiripan permukaan teks BUKAN bukti peniruan. Kandidat hanya dapat dicatat sebagai relasi 'kemiripan' "
                    "sampai ada bukti independen."}
