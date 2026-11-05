# LARAs — YOUTH-SNA

**Lacak Aktivitas Remaja di Ruang Siber · Youth Social Behavior Network Analytics**

Platform riset analisis jaringan sosial untuk menelaah bagaimana konten media sosial yang berpotensi
berbahaya bagi remaja **muncul, menyebar, mendapat perhatian, dan mungkin direplikasi** di TikTok,
Instagram, YouTube, dan X.

> **Bukan alat pengawasan atau profiling pelaku.** Aktor hanya disimpan sebagai pseudonim HMAC,
> label kategori melekat pada **konten** (bukan pada individu), sentralitas = posisi jaringan (bukan
> pengaruh psikologis atau tanggung jawab pidana), dan sistem tidak menyimpulkan usia, identitas,
> kondisi psikologis, atau niat pemilik akun.

Seluruh antarmuka berbahasa Indonesia. Dataset bawaan **SINTETIS (DEMO)**: semua akun, teks, dan peristiwa fiktif.

---

## Arsitektur

```
youth-sna/
├── backend/                 FastAPI · SQLAlchemy 2 · Alembic · NetworkX
│   ├── app/
│   │   ├── models.py        14 tabel riset (PostgreSQL; SQLite untuk pengembangan)
│   │   ├── sna.py           metrik SNA, Louvain, temporal, ekspor GraphML/GEXF/CSV
│   │   ├── graphs.py        3 lapisan jaringan dari DB + filter
│   │   ├── diffusion.py     aturan status bukti & kaskade difusi
│   │   ├── classifier.py    klasifikasi multi-label kontekstual (berbasis aturan, modular)
│   │   ├── textproc.py      normalisasi teks Indonesia (slang, ejaan, leetspeak) & kemiripan
│   │   ├── taxonomy.py      taksonomi K01–K08
│   │   ├── connectors/      YouTube, X, TikTok Research, Meta Content Library (placeholder), impor berkas
│   │   ├── ingest.py        validasi impor, pseudonimisasi, deduplikasi, eksekusi job
│   │   ├── synthetic.py     generator dataset DEMO (+ studi kasus ableisme)
│   │   ├── routers/         endpoint API per modul
│   │   └── worker.py        worker latar job pengumpulan
│   ├── migrations/          migrasi Alembic
│   └── tests/               49 uji (pytest)
├── frontend/                Next.js 15 · TypeScript · Tailwind · komponen gaya shadcn/ui · Cytoscape.js (fcose) · Recharts
└── docker-compose.yml       PostgreSQL · API · worker · web
```

## Menjalankan secara lokal (tanpa Docker)

Prasyarat: Python 3.11+ dan Node.js 20+.

```bash
# 1) Backend — basis data SQLite lokal + seed DEMO
cd youth-sna/backend
python -m venv .venv
.venv/Scripts/activate            # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --port 8000  # dokumentasi API: http://127.0.0.1:8000/docs
```

```bash
# 2) Frontend (terminal lain)
cd youth-sna/frontend
npm install
npm run dev                       # http://localhost:3000  (proksi /api → 127.0.0.1:8000)
```

```bash
# 3) Uji
cd youth-sna/backend
python -m pytest -q
```

### Akun demo (hanya mode DEMO, hanya untuk pengembangan lokal)

Kata sandi semua akun demo: `demo-laras-2026` (ubah lewat `YSNA_DEMO_PASSWORD` sebelum seed).

| Pengguna | Peran | Catatan |
|---|---|---|
| `ketua` | Peneliti Utama | taksonomi, sumber, ekspor teks, etika, retensi |
| `peneliti` | Peneliti | impor, job, ekspor anonim |
| `peninjau` | Peninjau / Anotator | validasi label & status bukti, menyetujui kesimpulan |
| `pengamat` | Pengamat | hanya baca; teks mentah disamarkan |
| `admin` | Administrator | semua izin + kelola pengguna |

Mode LIVE (`YSNA_DATA_MODE=LIVE`) tidak membuat akun demo; setel `YSNA_ADMIN_PASSWORD` untuk admin awal.

## Docker (PostgreSQL)

```bash
cd youth-sna
cp .env.example .env              # GANTI semua rahasia
docker compose up -d --build
docker compose exec api python -m app.seed
```

## Variabel lingkungan

| Variabel | Fungsi |
|---|---|
| `YSNA_DATABASE_URL` | mis. `postgresql+psycopg://laras:...@db:5432/laras` (bawaan: SQLite lokal) |
| `YSNA_JWT_SECRET` | rahasia token (wajib diganti) |
| `YSNA_PSEUDONYM_KEY` | kunci HMAC pseudonim — simpan aman; kehilangan kunci = pseudonim baru tidak cocok dengan yang lama |
| `YSNA_DATA_MODE` | `DEMO` atau `LIVE` |
| `YSNA_WORKER_MODE` | `inline` (BackgroundTasks API) atau `external` (`python -m app.worker`) |
| `YSNA_YOUTUBE_API_KEY` | YouTube Data API v3 |
| `YSNA_X_BEARER_TOKEN` | X API v2 |
| `YSNA_TIKTOK_CLIENT_KEY` / `YSNA_TIKTOK_CLIENT_SECRET` | TikTok Research API (hanya bila disetujui) |

---

## Status fitur

### ✅ Selesai (berfungsi end-to-end)

- **Network Explorer** (layar utama): graf force-directed (fcose), edge berarah & berbobot, zoom/pan, pencarian node,
  filter platform/kategori/tanggal/jenis interaksi/status bukti, ambang bobot edge, ukuran node dari metrik pilihan,
  warna komunitas/platform/kategori/konteks, klik untuk inspeksi, perluas tetangga (klik ganda), jalur terpendek,
  ekspor GraphML/GEXF/CSV/PNG, panel kanan (detail, metrik, kategori, node terhubung, linimasa, bukti, anotasi),
  panel bawah (aktivitas temporal, metrik jaringan, ekspor).
- **Tiga lapisan jaringan**: aktor–aktor, difusi konten–konten, partisipasi aktor–konten. Kemiripan ditandai terpisah
  (garis putus-putus) dan tidak pernah dihitung sebagai transmisi.
- **SNA (NetworkX)**: in/out-degree, betweenness, closeness (Wasserman–Faust), PageRank, Louvain + modularitas,
  densitas, komponen lemah/kuat, resiprositas, evolusi temporal mingguan. Penjelasan metrik berbahasa Indonesia.
- **Diffusion Tracker**: lini masa per platform, pertama teramati vs akar transmisi vs pencipta asli, 4 status bukti,
  bukti pendukung/bertentangan, indikator ketidakpastian, penambahan bukti, perubahan status **dibatasi oleh bukti**.
- **Studi kasus ableisme (DEMO, ABL-01)** + kasus tantangan berisiko (TTG-01) dan judi daring salin-tempel (JDL-01).
- **Content Intelligence**: taksonomi K01–K08 (definisi, inklusi/eksklusi, kata kunci dapat diedit & berversi, aturan kontekstual),
  klasifikasi multi-label kontekstual, antrean tinjauan manusia, uji klasifikasi, penemuan kata kunci, kemiripan semantik.
- **Actor Analytics** (tanpa papan peringkat; histogram distribusi), **Deteksi Komunitas**.
- **Basis data**: 14 tabel dengan PK/FK, indeks, unik, timestamp, provenance; migrasi Alembic; seed.
- **Impor CSV/JSON** dengan validasi per baris, uji coba (dry-run), normalisasi waktu ke UTC, pseudonimisasi, deduplikasi.
- **Autentikasi JWT & RBAC** 5 peran (ditegakkan di server), log audit, pseudonim HMAC, teks mentah dibatasi peran,
  retensi teks mentah, dokumentasi etika, kesimpulan wajib disetujui peninjau kedua, ekspor anonim (sensitif dikecualikan).
- **Uji unit**: fungsi jaringan, aturan bukti difusi, normalisasi & klasifikasi, impor, pseudonimisasi, API end-to-end.

### 🟡 Fungsional tetapi mock / baseline

- **Klasifier** = baseline berbasis aturan (`aturan-id-0.1.0`) di balik antarmuka `Classifier`; belum ada model terlatih.
- **Kemiripan semantik** = n-gram karakter + Jaccard token (tahan ejaan), bukan embedding.
- **Dataset** sepenuhnya sintetis; metrik dan komunitas mencerminkan generator, bukan kondisi nyata.
- **Konektor YouTube & X** terimplementasi sesuai dokumentasi resmi tetapi **belum diuji dengan kredensial nyata**.
- **Worker** = poller basis data sederhana (bukan Celery/Redis).

### 🔵 Integrasi mendatang

- **TikTok Research API**: klien siap, memerlukan persetujuan program TikTok untuk institusi.
- **Meta Content Library**: tidak ada REST API publik — placeholder berlabel; gunakan ekspor resmi dari lingkungan MCL → Impor.
- Model Transformer bahasa Indonesia (mis. IndoBERT) untuk klasifikasi; embedding teks/visual (hanya bila sah & diizinkan).
- Leiden (via `leidenalg`), Neo4j untuk kueri graf lanjutan bila data > jutaan edge, Redis/Celery, object storage media.
- Uji keamanan & performa, SSO institusi, rotasi kunci pseudonim.

## Prinsip etika yang ditegakkan kode

1. Handle, URL, dan ID platform **tidak disimpan** — hanya HMAC (`security.actor_hash`, `external_hash`).
2. Label klasifikasi melekat pada konten dan berstatus *belum ditinjau* sampai divalidasi manusia.
3. Konteks kontra-narasi, berita, edukasi, satire, dan pencegahan dibedakan dari konten berbahaya.
4. Kemiripan ≠ transmisi; status bukti tidak bisa melebihi yang didukung catatan bukti (`diffusion.max_supported_status`).
5. "Pertama teramati" dibedakan dari "pencipta asli".
6. Tidak ada papan peringkat yang mengidentifikasi individu; ekspor anonim & tercatat di audit.
7. Kesimpulan hanya diekspor setelah disetujui peninjau yang bukan penulisnya.
