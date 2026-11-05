"""Worker latar: menjalankan job pengumpulan berstatus 'antri'.

    YSNA_WORKER_MODE=external python -m app.worker
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select

from . import models as m
from .db import SessionLocal
from .ingest import run_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("laras.worker")


def run_once() -> int:
    with SessionLocal() as db:
        ids = list(db.scalars(select(m.CollectionJob.id).where(m.CollectionJob.status == "antri").order_by(m.CollectionJob.id).limit(5)))
    for jid in ids:
        with SessionLocal() as db:
            job = run_job(db, jid)
            log.info("job %s → %s (baru=%s, duplikat=%s)", jid, job.status if job else "?", getattr(job, "items_new", 0),
                     getattr(job, "items_duplicate", 0))
    return len(ids)


def main(poll_seconds: float = 5.0) -> None:
    log.info("Worker LARAs berjalan; polling setiap %.0f dtk.", poll_seconds)
    while True:
        try:
            if run_once() == 0:
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            break
        except Exception:  # noqa: BLE001
            log.exception("Kesalahan worker; lanjut.")
            time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
