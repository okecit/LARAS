"""Kerangka konektor sumber data resmi.

Setiap konektor:
- membaca kredensial dari variabel lingkungan (tidak pernah disimpan di DB),
- memeriksa otorisasi sebelum berjalan,
- menghormati rate limit & kuota (token bucket + penghitung kuota harian),
- mengembalikan `NormalizedItem` dengan asal-usul (provenance) dan waktu UTC.

Konektor TIDAK melewati autentikasi, tidak mengakses akun privat, dan tidak mengklaim izin yang tidak dimiliki.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

import httpx


class ConnectorError(Exception):
    pass


class NotAuthorized(ConnectorError):
    pass


class QuotaExceeded(ConnectorError):
    pass


class NotAvailable(ConnectorError):
    """Integrasi langsung tidak tersedia (gunakan alur impor resmi)."""


@dataclass
class NormalizedItem:
    platform: str
    external_id: str
    author_handle: str  # hanya untuk HMAC; dibuang setelah pseudonimisasi
    published_at: datetime  # UTC
    text: str
    content_type: str = "posting"
    metrics: dict[str, int] = field(default_factory=dict)
    parent_external_id: str | None = None
    parent_author_handle: str | None = None
    relation_type: str | None = None  # balasan_dari|repost_dari|kutipan_dari|remix_dari
    interaction_type: str | None = None  # komentar|balasan|bagikan|kutipan|remix|sebutan
    mentions: list[str] = field(default_factory=list)
    has_media: bool = False
    account_category: str = "tidak_diketahui"
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthStatus:
    status: str  # belum_dikonfigurasi|terkonfigurasi|terotorisasi|ditolak|memerlukan_persetujuan|tidak_tersedia
    message: str
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RateLimiter:
    """Token bucket sederhana (thread-safe)."""

    def __init__(self, rate_per_sec: float, burst: int = 1):
        self.rate, self.capacity = rate_per_sec, burst
        self.tokens, self.last = float(burst), time.monotonic()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                time.sleep((1 - self.tokens) / self.rate)


class QuotaTracker:
    def __init__(self, daily_limit: int | None, used: int = 0):
        self.limit, self.used = daily_limit, used

    def consume(self, units: int) -> None:
        if self.limit is not None and self.used + units > self.limit:
            raise QuotaExceeded(f"Kuota harian habis ({self.used}/{self.limit} unit).")
        self.used += units


def parse_timestamp(value: Any) -> datetime:
    """Normalisasi waktu ke UTC. Menerima ISO-8601 (dengan/ tanpa zona; tanpa zona dianggap UTC) atau epoch detik."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        dt = datetime.fromtimestamp(int(value), tz=timezone.utc)
    elif isinstance(value, str):
        s = value.strip().replace("Z", "+00:00")
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        dt = datetime.fromisoformat(s)
    else:
        raise ValueError(f"format waktu tidak dikenali: {value!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class BaseConnector:
    key: str = "base"
    platform: str = "lainnya"
    label: str = "Konektor"
    credential_envs: list[str] = []
    docs_url: str = ""
    availability: str = "tersedia"  # tersedia|memerlukan_persetujuan|placeholder
    notes: str = ""
    requests_per_sec: float = 1.0

    def __init__(self, quota: QuotaTracker | None = None, client: httpx.Client | None = None):
        self.quota = quota or QuotaTracker(None)
        self.limiter = RateLimiter(self.requests_per_sec)
        self.client = client or httpx.Client(timeout=30)
        self.log: list[dict[str, Any]] = []

    # ---------------------------------------------------------------- kredensial
    def credentials(self) -> dict[str, str | None]:
        return {name: os.getenv(name) for name in self.credential_envs}

    def is_configured(self) -> bool:
        return bool(self.credential_envs) and all(self.credentials().values())

    def check_authorization(self) -> AuthStatus:
        if self.availability == "placeholder":
            return AuthStatus("tidak_tersedia", self.notes)
        if not self.is_configured():
            missing = [k for k, v in self.credentials().items() if not v]
            return AuthStatus("belum_dikonfigurasi", f"Setel variabel lingkungan: {', '.join(missing)}")
        return AuthStatus("terkonfigurasi", "Kredensial tersedia (belum diverifikasi ke API).")

    # ---------------------------------------------------------------- HTTP dengan retry
    def _request(self, method: str, url: str, units: int = 1, **kw) -> httpx.Response:
        self.quota.consume(units)
        delay = 2.0
        for attempt in range(5):
            self.limiter.acquire()
            resp = self.client.request(method, url, **kw)
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = float(resp.headers.get("retry-after", delay))
                self.log_event("peringatan", f"HTTP {resp.status_code}; coba ulang dalam {wait:.0f} dtk (percobaan {attempt + 1}).")
                time.sleep(min(wait, 60))
                delay *= 2
                continue
            if resp.status_code in (401, 403):
                raise NotAuthorized(f"Akses ditolak ({resp.status_code}): {resp.text[:200]}")
            resp.raise_for_status()
            return resp
        raise ConnectorError(f"Gagal setelah 5 percobaan: {url}")

    def log_event(self, level: str, message: str) -> None:
        self.log.append({"at": datetime.now(timezone.utc).isoformat(), "level": level, "message": message})

    def fetch(self, query: str, params: dict[str, Any]) -> Iterator[NormalizedItem]:  # pragma: no cover - abstrak
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        auth = self.check_authorization()
        return {"key": self.key, "platform": self.platform, "label": self.label, "availability": self.availability,
                "credential_envs": self.credential_envs, "docs_url": self.docs_url, "notes": self.notes,
                "authorization": {"status": auth.status, "message": auth.message}}
