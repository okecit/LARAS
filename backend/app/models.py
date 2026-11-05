"""Skema basis data riset YOUTH-SNA (SQLAlchemy 2.0).

Prinsip:
- Fakta terkumpul (konten, interaksi) dipisah dari hasil mesin (klasifikasi) dan
  interpretasi peneliti (anotasi, bukti, status validasi).
- Aktor hanya disimpan sebagai pseudonim + HMAC; handle asli tidak pernah disimpan.
- Setiap baris data menyimpan asal-usul (source_id / provenance).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, TypeDecorator, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, utcnow


class UTCDateTime(TypeDecorator):
    """Simpan waktu sebagai UTC; selalu kembalikan datetime ber-zona UTC (juga di SQLite)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        if dialect.name == "sqlite":
            return value.replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False)


# --------------------------------------------------------------------------- proyek & pengguna

class ResearchProject(Timestamped, Base):
    __tablename__ = "research_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="aktif", nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Dokumentasi etika & persetujuan
    ethics_body: Mapped[Optional[str]] = mapped_column(String(200))
    ethics_approval_ref: Mapped[Optional[str]] = mapped_column(String(120))
    ethics_approval_date: Mapped[Optional[date]] = mapped_column(Date)
    consent_notes: Mapped[Optional[str]] = mapped_column(Text)
    data_minimization_notes: Mapped[Optional[str]] = mapped_column(Text)
    risk_mitigation_notes: Mapped[Optional[str]] = mapped_column(Text)
    # Retensi (hari): teks mentah dihapus lebih cepat dari data terolah
    raw_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=730, nullable=False)

    __table_args__ = (CheckConstraint("period_end >= period_start", name="ck_project_period"),)


class Platform(Base):
    __tablename__ = "platforms"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(24), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    color: Mapped[str] = mapped_column(String(9), default="#22d3ee", nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)


class ResearchUser(Timestamped, Base):
    __tablename__ = "research_users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)

    __table_args__ = (
        CheckConstraint("role in ('admin','peneliti_utama','peneliti','peninjau','pengamat')", name="ck_user_role"),
    )


# --------------------------------------------------------------------------- sumber & pengumpulan

class DataSource(Timestamped, Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # api | impor | demo
    connector_key: Mapped[str] = mapped_column(String(32), nullable=False)
    legal_basis: Mapped[str] = mapped_column(Text, nullable=False)  # ToS / perjanjian akses / izin etik
    access_level: Mapped[str] = mapped_column(String(24), default="terbatas", nullable=False)  # publik_agregat|terbatas|sensitif
    credential_env: Mapped[Optional[str]] = mapped_column(String(120))  # NAMA variabel env, bukan rahasianya
    authorization_status: Mapped[str] = mapped_column(String(32), default="belum_diperiksa", nullable=False)
    authorization_checked_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    quota_daily: Mapped[Optional[int]] = mapped_column(Integer)
    quota_used_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_reset_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    platform: Mapped[Platform] = relationship()

    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_source_project_name"),)


class CollectionJob(Timestamped, Base):
    __tablename__ = "collection_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="antri", nullable=False)  # antri|berjalan|selesai|gagal|dibatalkan
    query: Mapped[Optional[str]] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    requested_by: Mapped[Optional[int]] = mapped_column(ForeignKey("research_users.id", ondelete="SET NULL"))
    started_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    quota_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_log: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    source: Mapped[DataSource] = relationship()

    __table_args__ = (Index("ix_jobs_status", "status"),)


# --------------------------------------------------------------------------- aktor & konten

class PseudonymousActor(Timestamped, Base):
    __tablename__ = "pseudonymous_actors"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    pseudonym: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # HMAC-SHA256(handle) — tidak dapat dibalik tanpa kunci
    # Kategori akun hanya dari metadata publik (mis. akun media terverifikasi); TIDAK menebak usia/identitas.
    account_category: Mapped[str] = mapped_column(String(24), default="tidak_diketahui", nullable=False)
    follower_bucket: Mapped[Optional[str]] = mapped_column(String(16))
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    platform: Mapped[Platform] = relationship()

    __table_args__ = (
        UniqueConstraint("project_id", "platform_id", "actor_hash", name="uq_actor_hash"),
        UniqueConstraint("project_id", "pseudonym", name="uq_actor_pseudonym"),
    )


class ContentItem(Timestamped, Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("pseudonymous_actors.id", ondelete="CASCADE"), nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    collection_job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("collection_jobs.id", ondelete="SET NULL"))
    code: Mapped[str] = mapped_column(String(24), nullable=False)  # kode tampilan, mis. "KON-00042"
    external_id_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(16), nullable=False)  # video|posting|balasan|komentar|repost|kutipan|remix
    text_excerpt: Mapped[Optional[str]] = mapped_column(Text)  # data mentah terbatas; dihapus saat retensi
    text_normalized: Mapped[Optional[str]] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="id", nullable=False)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    published_tz_original: Mapped[Optional[str]] = mapped_column(String(16))
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    # Konteks: kandidat_berbahaya|kontra_narasi|berita|edukasi|satire|pencegahan|netral|tidak_jelas
    context_label: Mapped[str] = mapped_column(String(24), default="tidak_jelas", nullable=False)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_ref: Mapped[Optional[str]] = mapped_column(String(255))  # kunci object storage bila diizinkan
    access_level: Mapped[str] = mapped_column(String(24), default="terbatas", nullable=False)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_purged_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    actor: Mapped[PseudonymousActor] = relationship()
    platform: Mapped[Platform] = relationship()
    classifications: Mapped[list["ContentClassification"]] = relationship(back_populates="content", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("platform_id", "external_id_hash", name="uq_content_external"),
        UniqueConstraint("project_id", "code", name="uq_content_code"),
        Index("ix_content_project_published", "project_id", "published_at"),
        Index("ix_content_actor", "actor_id"),
    )


class ContentCategory(Timestamped, Base):
    __tablename__ = "content_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    name_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    inclusion_criteria: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    exclusion_criteria: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    keywords: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)  # [{term, weight}]
    context_rules: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    min_confidence: Mapped[float] = mapped_column(Float, default=0.35, nullable=False)
    color: Mapped[str] = mapped_column(String(9), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ContentClassification(Timestamped, Base):
    __tablename__ = "content_classifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("content_categories.id", ondelete="CASCADE"), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)  # aturan|model|manusia
    model_version: Mapped[str] = mapped_column(String(40), nullable=False)
    matched_terms: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    context_label: Mapped[str] = mapped_column(String(24), default="tidak_jelas", nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(20), default="belum_ditinjau", nullable=False)  # belum_ditinjau|valid|ditolak|direvisi
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("research_users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text)

    content: Mapped[ContentItem] = relationship(back_populates="classifications")
    category: Mapped[ContentCategory] = relationship()

    __table_args__ = (
        UniqueConstraint("content_id", "category_id", "model_version", name="uq_classification"),
        Index("ix_classification_status", "validation_status"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_classification_conf"),
    )


# --------------------------------------------------------------------------- relasi

class Interaction(Base):
    """Interaksi terdokumentasi antar-aktor (balasan, sebutan, bagikan, kutip, remix, komentar)."""

    __tablename__ = "interactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), nullable=False)
    source_actor_id: Mapped[int] = mapped_column(ForeignKey("pseudonymous_actors.id", ondelete="CASCADE"), nullable=False)
    target_actor_id: Mapped[int] = mapped_column(ForeignKey("pseudonymous_actors.id", ondelete="CASCADE"), nullable=False)
    content_id: Mapped[Optional[int]] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"))  # konten yang direspons
    response_content_id: Mapped[Optional[int]] = mapped_column(ForeignKey("content_items.id", ondelete="SET NULL"))
    interaction_type: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_id: Mapped[Optional[int]] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    external_id_hash: Mapped[Optional[str]] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("platform_id", "external_id_hash", name="uq_interaction_external"),
        Index("ix_interaction_project_time", "project_id", "occurred_at"),
        Index("ix_interaction_pair", "source_actor_id", "target_actor_id"),
    )


class ContentRelationship(Timestamped, Base):
    """Relasi konten→konten. `source` = konten lebih awal, `target` = konten turunan/respons.

    Kemiripan (relation_type='kemiripan') TIDAK PERNAH dianggap bukti transmisi.
    """

    __tablename__ = "content_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    source_content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    target_content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False)  # balasan_dari|repost_dari|kutipan_dari|remix_dari|lintas_platform|kemiripan
    evidence_status: Mapped[str] = mapped_column(String(28), nullable=False)  # kemiripan|kemungkinan_replikasi|replikasi_didukung|atribusi_terkonfirmasi
    is_platform_documented: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    similarity_score: Mapped[Optional[float]] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    time_lag_hours: Mapped[Optional[float]] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(32), default="metadata_platform", nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("research_users.id", ondelete="SET NULL"))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("source_content_id", "target_content_id", "relation_type", name="uq_content_rel"),
        CheckConstraint("source_content_id <> target_content_id", name="ck_rel_not_self"),
        Index("ix_rel_project", "project_id"),
    )


class EvidenceRecord(Timestamped, Base):
    __tablename__ = "evidence_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    relationship_id: Mapped[Optional[int]] = mapped_column(ForeignKey("content_relationships.id", ondelete="CASCADE"))
    content_id: Mapped[Optional[int]] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"))
    # metadata_platform|atribusi_eksplisit|kemiripan_teks|kemiripan_visual|audio_sama|urutan_waktu|perilaku_sebelumnya|celah_data|catatan_peneliti
    evidence_type: Mapped[str] = mapped_column(String(28), nullable=False)
    direction: Mapped[str] = mapped_column(String(14), nullable=False)  # mendukung|bertentangan|netral
    description: Mapped[str] = mapped_column(Text, nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    source_reference: Mapped[Optional[str]] = mapped_column(String(255))
    recorded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("research_users.id", ondelete="SET NULL"))

    __table_args__ = (
        CheckConstraint("relationship_id IS NOT NULL OR content_id IS NOT NULL", name="ck_evidence_target"),
        Index("ix_evidence_rel", "relationship_id"),
    )


# --------------------------------------------------------------------------- interpretasi & audit

class Annotation(Timestamped, Base):
    __tablename__ = "annotations"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("research_projects.id", ondelete="CASCADE"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(16), nullable=False)  # konten|aktor|relasi|komunitas|proyek
    target_id: Mapped[Optional[int]] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16), default="catatan", nullable=False)  # catatan|kode|kesimpulan
    author_id: Mapped[int] = mapped_column(ForeignKey("research_users.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    # Kesimpulan wajib ditinjau peninjau LAIN sebelum boleh dipublikasikan/diekspor
    review_status: Mapped[str] = mapped_column(String(16), default="draf", nullable=False)  # draf|perlu_tinjauan|disetujui|ditolak
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("research_users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)

    __table_args__ = (Index("ix_annotation_target", "target_type", "target_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("research_users.id", ondelete="SET NULL"))
    username: Mapped[Optional[str]] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(40))
    resource_id: Mapped[Optional[str]] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    __table_args__ = (Index("ix_audit_created", "created_at"),)
