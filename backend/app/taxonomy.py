"""Taksonomi perilaku konten K01–K08 (nilai awal; kata kunci & aturan dapat diubah peneliti)."""
from __future__ import annotations

# Penanda konteks yang membedakan konten berbahaya dari kritik, berita, edukasi, satire, pencegahan.
CONTEXT_MARKERS: dict[str, list[str]] = {
    "kontra_narasi": ["jangan", "stop", "tidak lucu", "gak lucu", "nggak lucu", "hentikan", "hargai", "hormati",
                      "tidak pantas", "gak pantas", "laporkan", "report aja", "miris", "malu", "tega", "kasihan banget",
                      "bukan bahan bercanda", "bukan candaan"],
    "berita": ["berita", "dilaporkan", "polisi", "kepolisian", "menurut keterangan", "redaksi", "liputan", "pihak sekolah",
               "diamankan", "kronologi", "dikonfirmasi"],
    "edukasi": ["edukasi", "mari belajar", "faktanya", "penjelasan", "kenapa ini berbahaya", "psikolog", "tips", "dampaknya",
                "perlu kamu tahu", "thread edukasi"],
    "satire": ["satire", "parodi", "sarkas", "/s"],
    "pencegahan": ["kampanye", "stopbullying", "hormatiperbedaan", "cegah", "pencegahan", "lindungi", "bijak bermedia",
                   "sekolah ramah", "saring sebelum sharing", "layanan aduan"],
}

# Pengali keyakinan "berbahaya" per konteks. Konten tetap dapat dikaitkan dengan topik kategori,
# tetapi konteks non-berbahaya menurunkan skor dan diberi label konteks.
CONTEXT_DAMPING = {"kontra_narasi": 0.3, "berita": 0.3, "edukasi": 0.25, "pencegahan": 0.2, "satire": 0.6}

CONTEXT_LABELS = {
    "kandidat_berbahaya": "Kandidat konten berbahaya",
    "kontra_narasi": "Kontra-narasi / kritik",
    "berita": "Pemberitaan",
    "edukasi": "Edukasi",
    "satire": "Satire / parodi",
    "pencegahan": "Kampanye pencegahan",
    "netral": "Netral",
    "tidak_jelas": "Tidak jelas",
}

_GENERIC_RULES = [
    {"rule": "konteks_kontra", "description": "Jika memuat penanda kontra-narasi/kritik, label konteks = kontra_narasi dan keyakinan berbahaya diturunkan."},
    {"rule": "konteks_berita", "description": "Pemberitaan faktual tentang peristiwa tidak diklasifikasikan sebagai konten berbahaya."},
    {"rule": "konteks_edukasi", "description": "Penjelasan bahaya/dampak untuk tujuan edukasi diberi label edukasi."},
    {"rule": "tinjauan_manusia", "description": "Semua label mesin berstatus 'belum ditinjau' sampai divalidasi peninjau."},
    {"rule": "bukan_label_individu", "description": "Label melekat pada KONTEN, bukan pada pemilik akun; tidak menyimpulkan kenakalan individu."},
]


def _kw(*terms: str, weight: float = 1.0) -> list[dict]:
    return [{"term": t, "weight": weight} for t in terms]


CATEGORIES: list[dict] = [
    {
        "code": "K01", "color": "#a78bfa",
        "name_id": "Perundungan dan Diskriminasi (termasuk ableisme)",
        "name_en": "Bullying and Discrimination (incl. ableism)",
        "definition": "Konten yang merendahkan, mengejek, mengucilkan, atau mendiskriminasi seseorang/kelompok berdasarkan "
                      "kondisi fisik, disabilitas, penampilan, status sosial, atau karakteristik lain, termasuk peniruan "
                      "gestur/cara bicara penyandang disabilitas untuk ditertawakan.",
        "inclusion_criteria": ["Ejekan atau olok-olok terhadap kondisi fisik/disabilitas", "Peniruan gestur disabilitas sebagai bahan tertawaan",
                               "Ajakan mengucilkan/mempermalukan seseorang", "Body shaming"],
        "exclusion_criteria": ["Kritik terhadap perilaku perundungan", "Edukasi tentang disabilitas", "Pemberitaan kasus perundungan",
                               "Konten advokasi oleh/atau bersama penyandang disabilitas"],
        "keywords": _kw("ejek", "olok", "ngatain", "body shaming", "bully", "dibully", "cacat", "pincang", "budek", "gaya jalan", "meniru",
                        "ketawain", "culun", "goblok", "idiot") + _kw("wkwk", "lucu banget", "difabel", "disabilitas", weight=0.4),
        "context_rules": _GENERIC_RULES + [{"rule": "ableisme_peniruan", "description": "Peniruan gestur/cara jalan + penanda tawa → kandidat ableisme; wajib tinjauan manusia."}],
    },
    {
        "code": "K02", "color": "#f87171",
        "name_id": "Kekerasan dan Intimidasi",
        "name_en": "Violence and Intimidation",
        "definition": "Konten yang menampilkan, mengajak, mengglorifikasi, atau mengancam tindakan kekerasan fisik, termasuk tawuran dan pengeroyokan.",
        "inclusion_criteria": ["Ajakan tawuran/duel", "Ancaman kekerasan terhadap orang tertentu", "Glorifikasi rekaman pengeroyokan"],
        "exclusion_criteria": ["Pemberitaan peristiwa kekerasan", "Konten bela diri/olahraga", "Fiksi yang jelas ditandai"],
        "keywords": _kw("tawuran", "keroyok", "dikeroyok", "hajar", "ancam", "gebukin", "sajam", "celurit", "duel", "labrak", "intimidasi")
                    + _kw("ribut", "pukul", "berantem", weight=0.5),
        "context_rules": _GENERIC_RULES,
    },
    {
        "code": "K03", "color": "#fbbf24",
        "name_id": "Tantangan Viral Berisiko",
        "name_en": "Risky Viral Challenges",
        "definition": "Konten yang mengajak atau menampilkan tantangan/tren yang berisiko menimbulkan cedera atau bahaya bagi pelaku maupun orang lain.",
        "inclusion_criteria": ["Ajakan ikut tantangan berbahaya", "Rekaman tantangan berisiko yang dipromosikan"],
        "exclusion_criteria": ["Peringatan bahaya tantangan", "Tantangan aman (mis. menari)"],
        "keywords": _kw("challenge berbahaya", "hadang truk", "stop truk", "nekat", "berani gak", "tantangan", "lompat dari")
                    + _kw("challenge", "ikut tren", "trend", weight=0.5),
        "context_rules": _GENERIC_RULES,
    },
    {
        "code": "K04", "color": "#38bdf8",
        "name_id": "Pelecehan dan Pelanggaran Privasi",
        "name_en": "Harassment and Privacy Violations",
        "definition": "Konten yang melecehkan (termasuk seksual) atau menyebarkan informasi/gambar pribadi seseorang tanpa izin.",
        "inclusion_criteria": ["Penyebaran foto/video pribadi tanpa izin", "Doxing (alamat, nomor telepon)", "Pelecehan verbal/seksual"],
        "exclusion_criteria": ["Edukasi keamanan digital", "Pemberitaan tanpa membuka identitas korban"],
        "keywords": _kw("sebar foto", "doxing", "alamat rumah", "nomor hp", "spill", "rekam diam-diam", "foto pribadi", "tanpa izin",
                        "catcalling", "pelecehan"),
        "context_rules": _GENERIC_RULES,
    },
    {
        "code": "K05", "color": "#2dd4bf",
        "name_id": "Vandalisme dan Pelanggaran Norma Sosial",
        "name_en": "Vandalism and Social Norm Violations",
        "definition": "Konten yang menampilkan atau mengajak perusakan fasilitas umum/milik orang lain atau pelanggaran norma sosial yang dibanggakan.",
        "inclusion_criteria": ["Pamer corat-coret/perusakan fasilitas umum", "Ajakan melanggar aturan publik secara demonstratif"],
        "exclusion_criteria": ["Seni mural berizin", "Pemberitaan perusakan"],
        "keywords": _kw("corat-coret", "vandal", "pilox", "merusak", "fasilitas umum", "rusak halte", "coret tembok") + _kw("bolos", "kabur sekolah", weight=0.5),
        "context_rules": _GENERIC_RULES,
    },
    {
        "code": "K06", "color": "#60a5fa",
        "name_id": "Judi dan Penipuan Digital",
        "name_en": "Gambling and Digital Fraud",
        "definition": "Konten yang mempromosikan judi daring, investasi/hadiah palsu, atau modus penipuan digital.",
        "inclusion_criteria": ["Promosi situs judi/slot", "Giveaway atau hadiah palsu", "Ajakan pinjaman/investasi ilegal"],
        "exclusion_criteria": ["Peringatan modus penipuan", "Pemberitaan penindakan judi daring"],
        "keywords": _kw("slot", "gacor", "maxwin", "judol", "togel", "scatter", "deposit", "giveaway palsu", "pinjol", "auto cuan") + _kw("link di bio", weight=0.5),
        "context_rules": _GENERIC_RULES,
    },
    {
        "code": "K07", "color": "#f472b6",
        "name_id": "Konten Berisiko Terkait Zat",
        "name_en": "Substance-Related Risky Content",
        "definition": "Konten yang menormalisasi, mempromosikan, atau mengajak penggunaan alkohol, rokok/vape, obat terlarang, atau zat berbahaya oleh kalangan muda.",
        "inclusion_criteria": ["Pamer/ajakan konsumsi miras atau oplosan", "Promosi vape kepada pelajar", "Normalisasi penyalahgunaan obat"],
        "exclusion_criteria": ["Edukasi bahaya zat", "Pemberitaan razia"],
        "keywords": _kw("miras", "oplosan", "mabuk", "ngelem", "pil koplo", "obat terlarang", "vape") + _kw("rokok", "alkohol", "nongkrong", weight=0.4),
        "context_rules": _GENERIC_RULES,
    },
    {
        "code": "K08", "color": "#fb923c",
        "name_id": "Ujaran Kebencian dan Intoleransi",
        "name_en": "Hate Speech and Intolerance",
        "definition": "Konten yang menyerang, merendahkan, atau mengajak memusuhi kelompok berdasarkan agama, suku, ras, gender, atau identitas lain.",
        "inclusion_criteria": ["Generalisasi negatif terhadap kelompok identitas", "Ajakan mengusir/memusuhi kelompok"],
        "exclusion_criteria": ["Diskusi akademik tentang intoleransi", "Kontra-narasi toleransi"],
        "keywords": _kw("usir mereka", "kaum mereka", "benci", "sesat", "intoleran", "antek", "bukan pribumi") + _kw("suku", "agama lain", weight=0.4),
        "context_rules": _GENERIC_RULES,
    },
]

CATEGORY_CODES = [c["code"] for c in CATEGORIES]
