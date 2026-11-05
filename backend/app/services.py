"""Layanan bersama: audit, pseudonimisasi aktor, klasifikasi tersimpan."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from .classifier import MODEL_VERSION, RuleClassifier
from .security import actor_hash, external_hash, pseudonym_for


def audit(db: Session, user: Optional[m.ResearchUser], action: str, resource_type: str | None = None,
          resource_id: Any = None, details: dict | None = None, ip: str | None = None) -> None:
    db.add(m.AuditLog(user_id=user.id if user else None, username=user.username if user else "sistem", action=action,
                      resource_type=resource_type, resource_id=str(resource_id) if resource_id is not None else None,
                      details=details or {}, ip_address=ip))


def current_project(db: Session) -> m.ResearchProject:
    proj = db.scalars(select(m.ResearchProject).order_by(m.ResearchProject.id)).first()
    if not proj:
        raise RuntimeError("Belum ada proyek riset. Jalankan `python -m app.seed`.")
    return proj


def platform_by_code(db: Session) -> dict[str, m.Platform]:
    return {p.code: p for p in db.scalars(select(m.Platform))}


def get_or_create_actor(db: Session, project: m.ResearchProject, platform: m.Platform, handle: str, *,
                        source_id: int | None = None, account_category: str = "tidak_diketahui",
                        follower_bucket: str | None = None, seen_at: datetime | None = None,
                        is_demo: bool = False) -> tuple[m.PseudonymousActor, bool]:
    """Kembalikan aktor berpseudonim; handle hanya dipakai untuk menghitung HMAC lalu dibuang."""
    h = actor_hash(platform.code, handle)
    actor = db.scalars(select(m.PseudonymousActor).where(
        m.PseudonymousActor.project_id == project.id, m.PseudonymousActor.platform_id == platform.id,
        m.PseudonymousActor.actor_hash == h)).first()
    created = False
    if actor is None:
        actor = m.PseudonymousActor(project_id=project.id, platform_id=platform.id, source_id=source_id,
                                    pseudonym=pseudonym_for(platform.code, h), actor_hash=h,
                                    account_category=account_category, follower_bucket=follower_bucket,
                                    first_seen_at=seen_at, last_seen_at=seen_at, is_demo=is_demo)
        db.add(actor)
        db.flush()
        created = True
    elif seen_at:
        if not actor.first_seen_at or seen_at < actor.first_seen_at:
            actor.first_seen_at = seen_at
        if not actor.last_seen_at or seen_at > actor.last_seen_at:
            actor.last_seen_at = seen_at
    return actor, created


def next_content_code(db: Session, project_id: int) -> str:
    n = db.scalar(select(func.count(m.ContentItem.id)).where(m.ContentItem.project_id == project_id)) or 0
    code = f"KON-{n + 1:05d}"
    while db.scalar(select(m.ContentItem.id).where(m.ContentItem.project_id == project_id, m.ContentItem.code == code)):
        n += 1
        code = f"KON-{n + 1:05d}"
    return code


def content_ext_hash(platform_code: str, external_id: str) -> str:
    return external_hash(platform_code, external_id)


def category_dicts(db: Session) -> list[dict]:
    return [{"id": c.id, "code": c.code, "keywords": c.keywords, "min_confidence": c.min_confidence, "is_active": c.is_active}
            for c in db.scalars(select(m.ContentCategory).order_by(m.ContentCategory.code))]


def classify_contents(db: Session, items: Iterable[m.ContentItem], classifier: RuleClassifier | None = None) -> int:
    """Klasifikasi ulang konten dengan model aturan; keputusan manusia (status selain belum_ditinjau) dipertahankan."""
    cats = category_dicts(db)
    clf = classifier or RuleClassifier(cats)
    id_by_code = {c["code"]: c["id"] for c in cats}
    n = 0
    items = list(items)
    existing: dict[tuple[int, int], m.ContentClassification] = {}
    ids = [it.id for it in items]
    for chunk in (ids[i:i + 500] for i in range(0, len(ids), 500)):
        for row in db.scalars(select(m.ContentClassification).where(
                m.ContentClassification.content_id.in_(chunk), m.ContentClassification.model_version == clf.version)):
            existing[(row.content_id, row.category_id)] = row
    for item in items:
        if not item.text_excerpt and item.text_normalized:
            res = clf.classify(item.text_normalized)
        else:
            res = clf.classify(item.text_excerpt or "")
        item.text_normalized = res.normalized_text
        item.context_label = res.context_label
        seen = set()
        for lab in res.labels:
            cid = id_by_code[lab.code]
            seen.add(cid)
            row = existing.get((item.id, cid))
            if row is None:
                db.add(m.ContentClassification(content_id=item.id, category_id=cid, confidence=lab.confidence, method="aturan",
                                               model_version=clf.version, matched_terms=lab.matched_terms,
                                               context_label=lab.context_label, rationale=lab.rationale))
            elif row.validation_status == "belum_ditinjau":
                row.confidence, row.matched_terms = lab.confidence, lab.matched_terms
                row.context_label, row.rationale = lab.context_label, lab.rationale
            n += 1
        for (cid_item, cid), row in existing.items():
            if cid_item == item.id and cid not in seen and row.validation_status == "belum_ditinjau":
                db.delete(row)
    return n


def mask_text(text: str | None, allowed: bool) -> str | None:
    if text is None:
        return None
    if allowed:
        return text
    return "[teks dibatasi — peran Anda tidak memiliki akses data mentah]"


__all__ = ["audit", "current_project", "platform_by_code", "get_or_create_actor", "classify_contents", "mask_text",
           "next_content_code", "content_ext_hash", "category_dicts", "MODEL_VERSION"]
