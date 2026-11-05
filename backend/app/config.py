"""Konfigurasi aplikasi dari variabel lingkungan (awalan YSNA_)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Muat .env sederhana (KEY=VALUE) tanpa dependensi tambahan."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

_DEV_SECRET = "dev-only-ganti-di-produksi"


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("YSNA_DATABASE_URL", f"sqlite:///{BASE_DIR / 'youth_sna.db'}"))
    jwt_secret: str = field(default_factory=lambda: os.getenv("YSNA_JWT_SECRET", _DEV_SECRET))
    pseudonym_key: str = field(default_factory=lambda: os.getenv("YSNA_PSEUDONYM_KEY", _DEV_SECRET + "-pseudonim"))
    token_minutes: int = field(default_factory=lambda: int(os.getenv("YSNA_TOKEN_MINUTES", "480")))
    # DEMO = data sintetis; LIVE = data hasil konektor/impor resmi
    data_mode: str = field(default_factory=lambda: os.getenv("YSNA_DATA_MODE", "DEMO").upper())
    # inline = job dijalankan oleh proses API (BackgroundTasks); external = oleh `python -m app.worker`
    worker_mode: str = field(default_factory=lambda: os.getenv("YSNA_WORKER_MODE", "inline"))
    cors_origins: list[str] = field(default_factory=lambda: os.getenv("YSNA_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","))
    max_import_bytes: int = field(default_factory=lambda: int(os.getenv("YSNA_MAX_IMPORT_BYTES", str(5 * 1024 * 1024))))

    @property
    def is_dev_secret(self) -> bool:
        return self.jwt_secret == _DEV_SECRET


settings = Settings()
