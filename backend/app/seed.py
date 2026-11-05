"""Isi basis data dengan proyek, taksonomi, pengguna demo, dan dataset SINTETIS.

    python -m app.seed            # isi bila kosong
    python -m app.seed --reset    # hapus semua data lalu isi ulang
"""
from __future__ import annotations

import argparse
import os
import random
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .db import Base, SessionLocal, engine
from .diffusion import Evidence, confidence_for
from .security import hash_password
from .services import audit, classify_contents, content_ext_hash, get_or_create_actor
from .synthetic import generate
from .taxonomy import CATEGORIES

PLATFORMS = [("tiktok", "TikTok", "#22d3ee"), ("instagram", "Instagram", "#c084fc"),
             ("youtube", "YouTube", "#f87171"), ("x", "X", "#e2e8f0"), ("lainnya", "Lainnya (impor)", "#94a3b8")]

# Akun DEMO lokal. Kata sandi demo hanya dibuat bila YSNA_DATA_MODE=DEMO.
DEMO_PASSWORD = os.getenv("YSNA_DEMO_PASSWORD", "demo-laras-2026")
DEMO_USERS = [("admin", "Admin Sistem", "admin"), ("ketua", "Peneliti Utama (Demo)", "peneliti_utama"),
              ("peneliti", "Peneliti (Demo)", "peneliti"), ("peninjau", "Peninjau (Demo)", "peninjau"),
              ("pengamat", "Pengamat (Demo)", "pengamat")]


def reset_db() -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed_reference(db: Session) -> m.ResearchProject:
    demo = settings.data_mode == "DEMO"
    proj = m.ResearchProject(
        code="LARAS-DEMO" if demo else "LARAS",
        name="LARAs — Studi Difusi Konten Perilaku Remaja" + (" (DEMO)" if demo else ""),
        description="Proyek demonstrasi dengan data SINTETIS sepenuhnya. Semua akun, teks, dan peristiwa fiktif.",
        period_start=date(2026, 7, 1), period_end=date(2026, 9, 30), is_demo=demo,
        ethics_body="Komisi Etik Penelitian (contoh)", ethics_approval_ref="KEP/DEMO/2026/001", ethics_approval_date=date(2026, 6, 15),
        consent_notes="Data publik platform; tidak ada interaksi dengan subjek. Persetujuan individual dikesampingkan oleh komisi etik "
                      "(contoh) dengan syarat pseudonimisasi, minimisasi, dan larangan publikasi kutipan yang dapat dilacak.",
        data_minimization_notes="Handle & URL tidak disimpan (HMAC). Teks mentah dibatasi peran dan dihapus setelah masa retensi mentah. "
                                "Tidak ada inferensi usia, identitas, kondisi psikologis, atau niat kriminal.",
        risk_mitigation_notes="Tidak ada papan peringkat individu. Kesimpulan wajib ditinjau peninjau kedua sebelum dipublikasikan.",
        raw_retention_days=90, retention_days=730)
    db.add(proj)
    for code, name, color in PLATFORMS:
        db.add(m.Platform(code=code, name=name, color=color))
    for c in CATEGORIES:
        db.add(m.ContentCategory(code=c["code"], name_id=c["name_id"], name_en=c["name_en"], definition=c["definition"],
                                 inclusion_criteria=c["inclusion_criteria"], exclusion_criteria=c["exclusion_criteria"],
                                 keywords=c["keywords"], context_rules=c["context_rules"], color=c["color"]))
    if settings.data_mode == "DEMO":
        for uname, display, role in DEMO_USERS:
            db.add(m.ResearchUser(username=uname, display_name=display, role=role, password_hash=hash_password(DEMO_PASSWORD)))
    else:
        admin_pw = os.getenv("YSNA_ADMIN_PASSWORD")
        if not admin_pw:
            raise SystemExit("Mode LIVE: setel YSNA_ADMIN_PASSWORD untuk membuat akun admin awal.")
        db.add(m.ResearchUser(username="admin", display_name="Administrator", role="admin", password_hash=hash_password(admin_pw)))
    db.flush()
    return proj


def seed_sources(db: Session, proj: m.ResearchProject, plats: dict[str, m.Platform]) -> dict[str, m.DataSource]:
    sources = {}
    spec = [
        ("tiktok", "Demo sintetis — TikTok", "demo", "demo", None),
        ("instagram", "Demo sintetis — Instagram", "demo", "demo", None),
        ("youtube", "Demo sintetis — YouTube", "demo", "demo", None),
        ("x", "Demo sintetis — X", "demo", "demo", None),
        ("youtube", "YouTube Data API v3", "api", "youtube", "YSNA_YOUTUBE_API_KEY"),
        ("tiktok", "TikTok Research API", "api", "tiktok_research", "YSNA_TIKTOK_CLIENT_KEY"),
        ("instagram", "Meta Content Library (ekspor resmi)", "api", "meta_content_library", None),
        ("x", "X API v2 — Recent Search", "api", "x_api", "YSNA_X_BEARER_TOKEN"),
        ("lainnya", "Impor CSV/JSON", "impor", "file_import", None),
    ]
    for plat, name, stype, key, env in spec:
        legal = ("Data sintetis buatan generator; tidak ada data nyata." if stype == "demo" else
                 "Wajib diisi: dasar hukum/ToS & nomor persetujuan akses sebelum job dijalankan.")
        s = m.DataSource(project_id=proj.id, platform_id=plats[plat].id, name=name, source_type=stype, connector_key=key,
                         legal_basis=legal, credential_env=env, access_level="terbatas",
                         authorization_status="demo" if stype == "demo" else "belum_diperiksa",
                         quota_daily={"youtube": 10000, "x_api": 500, "tiktok_research": 1000}.get(key))
        db.add(s)
        sources[name] = s
    db.flush()
    return sources


def seed_demo_data(db: Session) -> dict[str, int]:
    proj = seed_reference(db)
    plats = {p.code: p for p in db.scalars(select(m.Platform))}
    sources = seed_sources(db, proj, plats)
    demo_src = {p: sources[f"Demo sintetis — {plats[p].name}"] for p in ("tiktok", "instagram", "youtube", "x")}
    users = {u.username: u for u in db.scalars(select(m.ResearchUser))}

    ds = generate()
    now = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)

    # job pengumpulan historis (DEMO)
    for p, s in demo_src.items():
        db.add(m.CollectionJob(project_id=proj.id, source_id=s.id, status="selesai", query="dataset sintetis",
                               params={"generator_seed": 20261106}, started_at=now, finished_at=now + timedelta(minutes=2),
                               items_fetched=0, quota_used=0))
    db.add(m.CollectionJob(project_id=proj.id, source_id=sources["YouTube Data API v3"].id, status="gagal",
                           query="contoh job gagal (DEMO)", params={}, started_at=now, finished_at=now,
                           error_log=[{"at": now.isoformat(), "level": "error", "message": "Kredensial YSNA_YOUTUBE_API_KEY belum disetel (contoh)."}]))

    actor_rows: dict[str, m.PseudonymousActor] = {}
    for a in ds.actors:
        row, _ = get_or_create_actor(db, proj, plats[a.platform], a.key, source_id=demo_src[a.platform].id,
                                     account_category=a.account_category, follower_bucket=a.follower_bucket, is_demo=True)
        actor_rows[a.key] = row

    content_rows: dict[str, m.ContentItem] = {}
    n = 0
    for c in sorted(ds.contents, key=lambda x: x.published_at):
        n += 1
        actor = actor_rows[c.actor]
        row = m.ContentItem(project_id=proj.id, platform_id=plats[c.platform].id, actor_id=actor.id, source_id=demo_src[c.platform].id,
                            code=c.code or f"KON-{n:05d}", external_id_hash=content_ext_hash(c.platform, f"demo-{c.key}"),
                            content_type=c.content_type, text_excerpt=c.text, published_at=c.published_at,
                            published_tz_original="+07:00", collected_at=now, metrics=c.metrics, has_media=c.has_media,
                            is_demo=True, provenance={"generator": "synthetic.py", "seed": 20261106, "scenario": c.scenario, "key": c.key})
        db.add(row)
        content_rows[c.key] = row
        pub = c.published_at.astimezone(timezone.utc)
        if not actor.first_seen_at or pub < actor.first_seen_at:
            actor.first_seen_at = pub
        if not actor.last_seen_at or pub > actor.last_seen_at:
            actor.last_seen_at = pub
    db.flush()

    for it in ds.interactions:
        db.add(m.Interaction(project_id=proj.id, platform_id=plats[it.platform].id, source_actor_id=actor_rows[it.source].id,
                             target_actor_id=actor_rows[it.target].id,
                             content_id=content_rows[it.content].id if it.content else None,
                             response_content_id=content_rows[it.response].id if it.response else None,
                             interaction_type=it.itype, occurred_at=it.occurred_at, source_id=demo_src[it.platform].id,
                             is_demo=True, provenance={"generator": "synthetic.py"}))

    peninjau = users.get("peninjau")
    for r in ds.relations:
        src, tgt = content_rows[r.source], content_rows[r.target]
        lag = (tgt.published_at - src.published_at).total_seconds() / 3600
        ev = [Evidence(e["evidence_type"], e["direction"], e["strength"]) for e in r.evidence]
        sim = next((e["strength"] for e in r.evidence if e["evidence_type"] == "kemiripan_teks"), None)
        rel = m.ContentRelationship(project_id=proj.id, source_content_id=src.id, target_content_id=tgt.id,
                                    relation_type=r.relation_type, evidence_status=r.evidence_status,
                                    is_platform_documented=r.documented, similarity_score=sim,
                                    confidence=confidence_for(r.evidence_status, ev), time_lag_hours=round(lag, 2),
                                    method="metadata_platform" if r.documented else "tinjauan_peneliti", notes=r.notes)
        db.add(rel)
        db.flush()
        # Catatan bukti disimpan untuk relasi skenario; relasi latar cukup ditandai metadata platform.
        if src.provenance.get("scenario") or not r.documented:
            for e in r.evidence:
                db.add(m.EvidenceRecord(project_id=proj.id, relationship_id=rel.id, evidence_type=e["evidence_type"],
                                        direction=e["direction"], strength=e["strength"], description=e["description"],
                                        recorded_by=peninjau.id if peninjau else None))
    for e in ds.content_evidence:
        db.add(m.EvidenceRecord(project_id=proj.id, content_id=content_rows[e["content"]].id, evidence_type=e["evidence_type"],
                                direction=e["direction"], strength=e["strength"], description=e["description"],
                                recorded_by=peninjau.id if peninjau else None))
    db.flush()

    classify_contents(db, content_rows.values())
    db.flush()

    # sebagian label sudah ditinjau manusia (contoh alur validasi)
    rng = random.Random(7)
    rows = db.scalars(select(m.ContentClassification).order_by(m.ContentClassification.id)).all()
    for row in rows:
        r = rng.random()
        if r < 0.28:
            row.validation_status, row.reviewer_note = "valid", "Sesuai kriteria inklusi."
        elif r < 0.33:
            row.validation_status, row.reviewer_note = "ditolak", "Konteks bercanda antar-teman; tidak memenuhi kriteria inklusi."
        else:
            continue
        row.reviewer_id = peninjau.id if peninjau else None
        row.reviewed_at = now

    ketua = users.get("ketua")
    if ketua:
        abl_c1 = content_rows["C1"]
        db.add_all([
            m.Annotation(project_id=proj.id, target_type="konten", target_id=abl_c1.id, kind="kode", author_id=ketua.id,
                         body="Video C1 = titik percepatan (paling viral), bukan konten pertama yang teramati.", tags=["ABL-01", "titik_percepatan"]),
            m.Annotation(project_id=proj.id, target_type="proyek", kind="kesimpulan", author_id=ketua.id, review_status="perlu_tinjauan",
                         body="Pada kasus ABL-01, kontra-narasi (C5, C7, C8, C12) muncul dalam 2–20 hari dan menjangkau tayangan yang "
                              "sebanding dengan konten awal. Perlu validasi dengan data nyata.", tags=["ABL-01", "kontra_narasi"]),
            m.Annotation(project_id=proj.id, target_type="proyek", kind="kesimpulan", author_id=ketua.id, review_status="disetujui",
                         reviewed_by=peninjau.id if peninjau else None, reviewed_at=now,
                         body="Relasi lintas platform TikTok→YouTube pada ABL-01 dan TTG-01 terdokumentasi melalui atribusi eksplisit.",
                         tags=["lintas_platform"]),
        ])
    audit(db, None, "seed_demo", "proyek", proj.id, {"actors": len(actor_rows), "contents": len(content_rows),
                                                     "interactions": len(ds.interactions), "relations": len(ds.relations)})
    return {"actors": len(actor_rows), "contents": len(content_rows), "interactions": len(ds.interactions), "relations": len(ds.relations)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="hapus semua tabel lalu isi ulang")
    ap.add_argument("--create-tables", action="store_true", help="buat tabel tanpa Alembic (pengembangan)")
    args = ap.parse_args()
    if args.reset:
        reset_db()
    elif args.create_tables:
        Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalars(select(m.ResearchProject)).first():
            print("Basis data sudah berisi proyek; gunakan --reset untuk mengisi ulang.")
            return
        if settings.data_mode == "DEMO":
            stats = seed_demo_data(db)
        else:
            seed_reference(db)
            stats = {}
        db.commit()
    print("Seed selesai:", stats)


if __name__ == "__main__":
    main()
