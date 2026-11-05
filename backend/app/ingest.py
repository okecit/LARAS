"""Penyimpanan item ternormalisasi: deduplikasi, pseudonimisasi, relasi terdokumentasi, klasifikasi.
Juga validasi berkas impor CSV/JSON dan eksekusi job pengumpulan."""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .connectors import ConnectorError, NormalizedItem, QuotaTracker, get_connector, parse_timestamp
from .security import external_hash
from .services import audit, classify_contents, get_or_create_actor, next_content_code, platform_by_code

VALID_PLATFORMS = {"tiktok", "instagram", "youtube", "x", "lainnya"}
VALID_CONTENT_TYPES = {"video", "posting", "balasan", "komentar", "repost", "kutipan", "remix"}
VALID_INTERACTIONS = {"komentar", "balasan", "bagikan", "kutipan", "remix", "sebutan"}
REL_FOR_INTERACTION = {"komentar": "balasan_dari", "balasan": "balasan_dari", "kutipan": "kutipan_dari", "remix": "remix_dari",
                       "bagikan": "repost_dari"}
REQUIRED_FIELDS = ["platform", "external_id", "author_handle", "published_at", "text"]
MAX_TEXT = 5000

IMPORT_TEMPLATE_FIELDS = REQUIRED_FIELDS + ["content_type", "parent_external_id", "parent_author_handle", "interaction_type",
                                            "views", "likes", "comments", "shares", "has_media"]


@dataclass
class IngestStats:
    fetched: int = 0
    new: int = 0
    duplicate: int = 0
    rejected: int = 0
    relations: int = 0
    interactions: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ValidationReport:
    valid: list[NormalizedItem]
    errors: list[dict[str, Any]]
    total_rows: int
    duplicates_in_file: int

    def as_dict(self) -> dict[str, Any]:
        return {"total_rows": self.total_rows, "valid_rows": len(self.valid), "invalid_rows": len({e["row"] for e in self.errors}),
                "duplicates_in_file": self.duplicates_in_file, "errors": self.errors[:200],
                "preview": [{"platform": v.platform, "published_at": v.published_at.isoformat(), "content_type": v.content_type,
                             "text": v.text[:120], "relation": v.relation_type} for v in self.valid[:10]]}


def parse_import_file(filename: str, raw: bytes, default_platform: str | None = None) -> ValidationReport:
    text = raw.decode("utf-8-sig")
    rows: list[dict[str, Any]]
    if filename.lower().endswith(".json"):
        data = json.loads(text)
        rows = data["items"] if isinstance(data, dict) and "items" in data else data
        if not isinstance(rows, list):
            raise ValueError("JSON harus berupa daftar objek atau {\"items\": [...]}.")
    elif filename.lower().endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        raise ValueError("Format berkas harus .csv atau .json")
    valid, errors, seen, dups = [], [], set(), 0
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append({"row": i, "field": "*", "message": "baris bukan objek"})
            continue
        row = {k.strip().lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        if default_platform and not row.get("platform"):
            row["platform"] = default_platform
        errs = []
        for f in REQUIRED_FIELDS:
            if row.get(f) in (None, ""):
                errs.append({"row": i, "field": f, "message": "wajib diisi"})
        plat = str(row.get("platform", "")).lower()
        if plat and plat not in VALID_PLATFORMS:
            errs.append({"row": i, "field": "platform", "message": f"harus salah satu dari {sorted(VALID_PLATFORMS)}"})
        ctype = str(row.get("content_type") or "posting").lower()
        if ctype not in VALID_CONTENT_TYPES:
            errs.append({"row": i, "field": "content_type", "message": f"harus salah satu dari {sorted(VALID_CONTENT_TYPES)}"})
        itype = (row.get("interaction_type") or None)
        if itype and itype not in VALID_INTERACTIONS:
            errs.append({"row": i, "field": "interaction_type", "message": f"harus salah satu dari {sorted(VALID_INTERACTIONS)}"})
        if itype and not row.get("parent_external_id"):
            errs.append({"row": i, "field": "parent_external_id", "message": "wajib bila interaction_type diisi"})
        ts = None
        if row.get("published_at"):
            try:
                ts = parse_timestamp(row["published_at"])
            except (ValueError, OverflowError):
                errs.append({"row": i, "field": "published_at", "message": "format waktu tidak valid (pakai ISO-8601 atau epoch)"})
        text_v = str(row.get("text") or "")
        if len(text_v) > MAX_TEXT:
            errs.append({"row": i, "field": "text", "message": f"lebih dari {MAX_TEXT} karakter"})
        metrics = {}
        for src, dst in [("views", "tayangan"), ("likes", "suka"), ("comments", "komentar"), ("shares", "bagikan")]:
            if row.get(src) not in (None, ""):
                try:
                    metrics[dst] = int(float(row[src]))
                except (TypeError, ValueError):
                    errs.append({"row": i, "field": src, "message": "harus angka"})
        if errs:
            errors.extend(errs)
            continue
        key = (plat, str(row["external_id"]))
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        valid.append(NormalizedItem(
            platform=plat, external_id=str(row["external_id"]), author_handle=str(row["author_handle"]), published_at=ts,
            text=text_v, content_type=ctype, metrics=metrics, parent_external_id=row.get("parent_external_id") or None,
            parent_author_handle=row.get("parent_author_handle") or None,
            relation_type=REL_FOR_INTERACTION.get(itype) if itype else None, interaction_type=itype,
            has_media=str(row.get("has_media", "")).lower() in ("1", "true", "ya", "yes"),
            provenance={"import_file": filename, "row": i}))
    return ValidationReport(valid, errors, len(rows), dups)


def ingest_items(db: Session, project: m.ResearchProject, source: m.DataSource, items: Iterable[NormalizedItem],
                 job: m.CollectionJob | None = None) -> IngestStats:
    stats = IngestStats()
    plats = platform_by_code(db)
    new_contents: list[m.ContentItem] = []
    pending_links: list[tuple[m.ContentItem, NormalizedItem]] = []
    for it in items:
        stats.fetched += 1
        plat = plats.get(it.platform)
        if plat is None:
            stats.rejected += 1
            stats.errors.append({"external_id_hash": external_hash(it.platform, it.external_id)[:12], "message": "platform tidak dikenal"})
            continue
        ext = external_hash(plat.code, it.external_id)
        if db.scalar(select(m.ContentItem.id).where(m.ContentItem.platform_id == plat.id, m.ContentItem.external_id_hash == ext)):
            stats.duplicate += 1
            continue
        actor, _ = get_or_create_actor(db, project, plat, it.author_handle, source_id=source.id,
                                       account_category=it.account_category, seen_at=it.published_at, is_demo=False)
        content = m.ContentItem(project_id=project.id, platform_id=plat.id, actor_id=actor.id, source_id=source.id,
                                collection_job_id=job.id if job else None, code=next_content_code(db, project.id),
                                external_id_hash=ext, content_type=it.content_type, text_excerpt=it.text[:MAX_TEXT],
                                published_at=it.published_at, collected_at=datetime.now(timezone.utc), metrics=it.metrics,
                                has_media=it.has_media, access_level=source.access_level, is_demo=False,
                                provenance={**it.provenance, "source": source.name, "connector": source.connector_key})
        db.add(content)
        db.flush()
        new_contents.append(content)
        stats.new += 1
        if it.parent_external_id:
            pending_links.append((content, it))
    # relasi dibuat setelah semua konten ada, agar urutan baris tidak berpengaruh
    for content, it in pending_links:
        plat = plats[it.platform]
        parent = db.scalars(select(m.ContentItem).where(m.ContentItem.platform_id == plat.id,
                                                        m.ContentItem.external_id_hash == external_hash(plat.code, it.parent_external_id))).first()
        target_actor_id = parent.actor_id if parent else None
        if target_actor_id is None and it.parent_author_handle:
            pa, _ = get_or_create_actor(db, project, plat, it.parent_author_handle, source_id=source.id)
            target_actor_id = pa.id
        if parent and it.relation_type:
            db.add(m.ContentRelationship(project_id=project.id, source_content_id=parent.id, target_content_id=content.id,
                                         relation_type=it.relation_type, evidence_status="atribusi_terkonfirmasi",
                                         is_platform_documented=True, confidence=0.95, method="metadata_platform",
                                         time_lag_hours=round((content.published_at - parent.published_at).total_seconds() / 3600, 2)))
            stats.relations += 1
        if target_actor_id and it.interaction_type and target_actor_id != content.actor_id:
            db.add(m.Interaction(project_id=project.id, platform_id=plat.id, source_actor_id=content.actor_id,
                                 target_actor_id=target_actor_id, content_id=parent.id if parent else None,
                                 response_content_id=content.id, interaction_type=it.interaction_type,
                                 occurred_at=content.published_at, source_id=source.id,
                                 external_id_hash=external_hash(plat.code, f"int:{it.external_id}"),
                                 provenance={"derived_from": "metadata_platform"}))
            stats.interactions += 1
    db.flush()
    classify_contents(db, new_contents)
    return stats


def run_job(db: Session, job_id: int) -> m.CollectionJob:
    """Eksekusi satu job pengumpulan (dipanggil worker atau BackgroundTasks)."""
    job = db.get(m.CollectionJob, job_id)
    if job is None or job.status not in ("antri",):
        return job
    source = job.source
    project = db.get(m.ResearchProject, job.project_id)
    job.status, job.started_at = "berjalan", datetime.now(timezone.utc)
    db.commit()
    today = datetime.now(timezone.utc).date()
    if source.quota_reset_at is None or source.quota_reset_at.date() < today:
        source.quota_used_today, source.quota_reset_at = 0, datetime.now(timezone.utc)
    connector = get_connector(source.connector_key, quota=QuotaTracker(source.quota_daily, source.quota_used_today))
    try:
        if "wajib diisi" in (source.legal_basis or "").lower():
            raise ConnectorError("Dasar hukum/ToS sumber belum diisi; job ditolak.")
        stats = ingest_items(db, project, source, connector.fetch(job.query or "", job.params or {}), job)
        job.items_fetched, job.items_new, job.items_duplicate, job.items_rejected = stats.fetched, stats.new, stats.duplicate, stats.rejected
        job.status = "selesai"
        job.error_log = connector.log + stats.errors
    except Exception as e:  # noqa: BLE001 - semua kegagalan dicatat pada job
        db.rollback()
        job = db.get(m.CollectionJob, job_id)
        job.status = "gagal"
        job.error_log = connector.log + [{"at": datetime.now(timezone.utc).isoformat(), "level": "error",
                                          "message": f"{type(e).__name__}: {e}"}]
    job.quota_used = connector.quota.used - (source.quota_used_today or 0)
    source.quota_used_today = connector.quota.used
    job.finished_at = datetime.now(timezone.utc)
    audit(db, None, "job_selesai" if job.status == "selesai" else "job_gagal", "collection_job", job.id,
          {"new": job.items_new, "dup": job.items_duplicate})
    db.commit()
    return job
