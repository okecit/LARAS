"""Diffusion Tracker: kasus kaskade, relasi konten, dan catatan bukti."""
from __future__ import annotations

from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..cache import bump
from ..db import get_db
from ..deps import client_ip, require
from ..diffusion import (EVIDENCE_DESCRIPTIONS, EVIDENCE_LABELS, EVIDENCE_STATUSES, Evidence, build_cascade, cascade_components,
                         clamp_status, confidence_for, max_supported_status)
from ..graphs import content_categories
from ..security import has_permission
from ..services import audit, current_project, mask_text
from ..textproc import similarity

router = APIRouter(prefix="/api/diffusion", tags=["diffusion"])

SCENARIO_TITLES = {"ABL-01": "Studi kasus ableisme: tren meniru gaya jalan (DEMO)",
                   "TTG-01": "Tantangan viral berisiko: hadang truk (DEMO)",
                   "JDL-01": "Promosi judi daring salin-tempel (DEMO)"}


def _cases(db: Session, project_id: int) -> list[dict]:
    rels = db.execute(select(m.ContentRelationship.source_content_id, m.ContentRelationship.target_content_id)
                      .where(m.ContentRelationship.project_id == project_id)).all()
    comps = cascade_components([(a, b) for a, b in rels], min_size=4)
    contents = {c.id: c for c in db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == project_id))}
    plats = {p.id: p.code for p in db.scalars(select(m.Platform))}
    ccats = content_categories(db, project_id)
    out = []
    for comp in comps:
        items = [contents[i] for i in comp if i in contents]
        scen = Counter((c.provenance or {}).get("scenario") for c in items).most_common(1)[0][0]
        first = min(items, key=lambda c: c.published_at)
        cats = Counter(cat for c in items for cat in ccats.get(c.id, []))
        case_id = scen or f"KAS-{first.code}"
        out.append({"id": case_id, "title": SCENARIO_TITLES.get(scen, f"Kaskade dari {first.code}"), "size": len(items),
                    "platforms": sorted({plats[c.platform_id] for c in items}), "first_observed": first.code,
                    "first_observed_at": first.published_at.isoformat(), "dominant_categories": [k for k, _ in cats.most_common(2)],
                    "content_ids": sorted(comp), "is_scenario": bool(scen)})
    out.sort(key=lambda c: (not c["is_scenario"], -c["size"]))
    return out


@router.get("/cases")
def cases(db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    return [{k: v for k, v in c.items() if k != "content_ids"} for c in _cases(db, proj.id)]


@router.get("/cascade/{case_id}")
def cascade(case_id: str, include_similarity: bool = True, db: Session = Depends(get_db), user=Depends(require("view"))):
    proj = current_project(db)
    case = next((c for c in _cases(db, proj.id) if c["id"] == case_id), None)
    if not case:
        raise HTTPException(404, "Kasus tidak ditemukan.")
    ids = set(case["content_ids"])
    can_raw = has_permission(user.role, "view_raw")
    plats = {p.id: p.code for p in db.scalars(select(m.Platform))}
    ccats = content_categories(db, proj.id)
    contents = {c.id: c for c in db.scalars(select(m.ContentItem).where(m.ContentItem.id.in_(ids)))}
    rels = db.scalars(select(m.ContentRelationship).where(m.ContentRelationship.source_content_id.in_(ids),
                                                          m.ContentRelationship.target_content_id.in_(ids))).all()
    ev_rows = db.scalars(select(m.EvidenceRecord).where(m.EvidenceRecord.relationship_id.in_([r.id for r in rels] or [0]))).all()
    content_ev = db.scalars(select(m.EvidenceRecord).where(m.EvidenceRecord.content_id.in_(ids))).all()
    ev_by_rel: dict[int, list[m.EvidenceRecord]] = {}
    for e in ev_rows:
        ev_by_rel.setdefault(e.relationship_id, []).append(e)
    items = [{"id": f"c{c.id}", "code": c.code, "platform": plats[c.platform_id], "published_at": c.published_at,
              "actor": c.actor.pseudonym, "actor_id": f"a{c.actor_id}", "content_type": c.content_type, "context_label": c.context_label,
              "categories": ccats.get(c.id, []), "metrics": c.metrics, "text": mask_text(c.text_excerpt, can_raw)}
             for c in contents.values()]
    relations = []
    for r in rels:
        if r.evidence_status == "kemiripan" and not include_similarity:
            continue
        evs = ev_by_rel.get(r.id, [])
        relations.append({"id": r.id, "source": f"c{r.source_content_id}", "target": f"c{r.target_content_id}",
                          "relation_type": r.relation_type, "evidence_status": r.evidence_status,
                          "evidence_label": EVIDENCE_LABELS[r.evidence_status], "documented": r.is_platform_documented,
                          "confidence": r.confidence, "similarity_score": r.similarity_score, "time_lag_hours": r.time_lag_hours,
                          "notes": r.notes, "supporting": sum(1 for e in evs if e.direction == "mendukung"),
                          "contradicting": sum(1 for e in evs if e.direction == "bertentangan"),
                          "evidence": [{"id": e.id, "type": e.evidence_type, "direction": e.direction, "strength": e.strength,
                                        "description": e.description} for e in evs]})
    result = build_cascade(items, relations)
    result["case"] = {k: v for k, v in case.items() if k != "content_ids"}
    result["content_evidence"] = [{"content_id": f"c{e.content_id}", "type": e.evidence_type, "direction": e.direction,
                                   "description": e.description} for e in content_ev]
    result["evidence_statuses"] = [{"code": s, "label": EVIDENCE_LABELS[s], "description": EVIDENCE_DESCRIPTIONS[s]} for s in EVIDENCE_STATUSES]
    return result


class RelationIn(BaseModel):
    source_content_id: int
    target_content_id: int
    relation_type: str = Field("kemiripan", pattern="^(balasan_dari|repost_dari|kutipan_dari|remix_dari|lintas_platform|kemiripan)$")
    requested_status: str = Field("kemiripan", pattern="^(kemiripan|kemungkinan_replikasi|replikasi_didukung|atribusi_terkonfirmasi)$")
    notes: str | None = None


@router.post("/relations")
def create_relation(body: RelationIn, request: Request, db: Session = Depends(get_db), user=Depends(require("edit_evidence"))):
    """Relasi baru dari peneliti selalu dimulai pada status yang didukung bukti (tanpa bukti → 'kemiripan')."""
    proj = current_project(db)
    s, t = db.get(m.ContentItem, body.source_content_id), db.get(m.ContentItem, body.target_content_id)
    if not s or not t or s.id == t.id:
        raise HTTPException(422, "Konten sumber/target tidak valid.")
    order_ok = t.published_at >= s.published_at
    status = clamp_status(body.requested_status, [], order_ok)
    sim = similarity(s.text_excerpt or "", t.text_excerpt or "") if s.text_excerpt and t.text_excerpt else None
    rel = m.ContentRelationship(project_id=proj.id, source_content_id=s.id, target_content_id=t.id, relation_type=body.relation_type,
                                evidence_status=status, is_platform_documented=False, similarity_score=sim,
                                confidence=confidence_for(status, []), method="tinjauan_peneliti", created_by=user.id,
                                time_lag_hours=round((t.published_at - s.published_at).total_seconds() / 3600, 2), notes=body.notes)
    db.add(rel)
    db.flush()
    audit(db, user, "buat_relasi", "relasi", rel.id, {"diminta": body.requested_status, "ditetapkan": status}, client_ip(request))
    db.commit()
    bump()
    return {"id": rel.id, "evidence_status": status, "clamped": status != body.requested_status,
            "message": None if status == body.requested_status else "Status dibatasi oleh bukti yang ada. Tambahkan catatan bukti lalu ajukan ulang."}


class EvidenceIn(BaseModel):
    evidence_type: str = Field(..., pattern="^(metadata_platform|atribusi_eksplisit|kemiripan_teks|kemiripan_visual|audio_sama|tagar_tren|urutan_waktu|perilaku_sebelumnya|celah_data|catatan_peneliti)$")
    direction: str = Field(..., pattern="^(mendukung|bertentangan|netral)$")
    strength: float = Field(0.5, ge=0, le=1)
    description: str = Field(..., min_length=5, max_length=2000)
    source_reference: str | None = None


@router.post("/relations/{rel_id}/evidence")
def add_evidence(rel_id: int, body: EvidenceIn, request: Request, db: Session = Depends(get_db), user=Depends(require("edit_evidence"))):
    rel = db.get(m.ContentRelationship, rel_id)
    if not rel:
        raise HTTPException(404, "Relasi tidak ditemukan.")
    db.add(m.EvidenceRecord(project_id=rel.project_id, relationship_id=rel.id, recorded_by=user.id, **body.model_dump()))
    db.flush()
    allowed = _allowed_status(db, rel)
    # Bila bukti bertentangan menurunkan batas, status diturunkan otomatis.
    if EVIDENCE_STATUSES.index(rel.evidence_status) > EVIDENCE_STATUSES.index(allowed):
        rel.evidence_status = allowed
    rel.confidence = confidence_for(rel.evidence_status, _evidence(db, rel))
    audit(db, user, "tambah_bukti", "relasi", rel.id, {"type": body.evidence_type, "direction": body.direction}, client_ip(request))
    db.commit()
    bump()
    return {"id": rel.id, "evidence_status": rel.evidence_status, "max_supported_status": allowed, "confidence": rel.confidence}


class StatusIn(BaseModel):
    evidence_status: str = Field(..., pattern="^(kemiripan|kemungkinan_replikasi|replikasi_didukung|atribusi_terkonfirmasi)$")


@router.patch("/relations/{rel_id}/status")
def set_status(rel_id: int, body: StatusIn, request: Request, db: Session = Depends(get_db), user=Depends(require("validate"))):
    rel = db.get(m.ContentRelationship, rel_id)
    if not rel:
        raise HTTPException(404, "Relasi tidak ditemukan.")
    allowed = _allowed_status(db, rel)
    if EVIDENCE_STATUSES.index(body.evidence_status) > EVIDENCE_STATUSES.index(allowed):
        raise HTTPException(422, f"Bukti saat ini hanya mendukung status '{EVIDENCE_LABELS[allowed]}'.")
    before = rel.evidence_status
    rel.evidence_status = body.evidence_status
    rel.confidence = confidence_for(rel.evidence_status, _evidence(db, rel))
    audit(db, user, "ubah_status_bukti", "relasi", rel.id, {"dari": before, "ke": body.evidence_status}, client_ip(request))
    db.commit()
    bump()
    return {"id": rel.id, "evidence_status": rel.evidence_status, "confidence": rel.confidence}


def _evidence(db: Session, rel: m.ContentRelationship) -> list[Evidence]:
    return [Evidence(e.evidence_type, e.direction, e.strength)
            for e in db.scalars(select(m.EvidenceRecord).where(m.EvidenceRecord.relationship_id == rel.id))]


def _allowed_status(db: Session, rel: m.ContentRelationship) -> str:
    s, t = db.get(m.ContentItem, rel.source_content_id), db.get(m.ContentItem, rel.target_content_id)
    ev = _evidence(db, rel)
    if rel.is_platform_documented:
        ev.append(Evidence("metadata_platform", "mendukung", 1.0))
    return max_supported_status(ev, t.published_at >= s.published_at)
