"""Generator dataset SINTETIS (DEMO) — semua akun, teks, dan peristiwa fiktif.

Struktur:
1. Latar: 7 kelompok laten (komunitas) dengan interaksi yang lebih rapat di dalam kelompok.
2. Kasus difusi terskrip:
   - ABL-01  Studi kasus ableisme lintas platform (TikTok → IG/X/YouTube), termasuk kontra-narasi,
             edukasi, berita, pencegahan, satire, bukti pendukung & bertentangan.
   - TTG-01  Tantangan viral berisiko "hadang truk".
   - JDL-01  Promosi judi daring salin-tempel (hanya kemiripan / kemungkinan replikasi).
Hasil fungsi berupa dict biasa; penyimpanan ke DB dilakukan di `seed.py`.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

WIB = timezone(timedelta(hours=7))
PERIOD_START = datetime(2026, 7, 1, tzinfo=WIB)
PERIOD_END = datetime(2026, 9, 30, 23, 59, tzinfo=WIB)
SEED = 20261106


@dataclass
class SActor:
    key: str
    platform: str
    group: str
    account_category: str = "individu"
    follower_bucket: str = "1rb–10rb"


@dataclass
class SContent:
    key: str
    actor: str
    platform: str
    published_at: datetime
    content_type: str
    text: str
    metrics: dict[str, int] = field(default_factory=dict)
    has_media: bool = False
    scenario: str | None = None
    code: str | None = None


@dataclass
class SInteraction:
    source: str  # aktor
    target: str  # aktor
    content: str | None
    response: str | None
    itype: str
    occurred_at: datetime
    platform: str


@dataclass
class SRelation:
    source: str  # konten lebih awal
    target: str
    relation_type: str
    evidence_status: str
    documented: bool
    evidence: list[dict[str, Any]] = field(default_factory=list)
    notes: str | None = None


@dataclass
class SDataset:
    actors: list[SActor] = field(default_factory=list)
    contents: list[SContent] = field(default_factory=list)
    interactions: list[SInteraction] = field(default_factory=list)
    relations: list[SRelation] = field(default_factory=list)
    content_evidence: list[dict[str, Any]] = field(default_factory=list)


GROUPS: dict[str, dict[str, Any]] = {
    "G0": {"name": "Hiburan & tren", "platforms": {"tiktok": 0.7, "instagram": 0.3}, "n": 30, "cats": {"K01": 0.5, "K03": 0.5}, "harm": 0.7},
    "G1": {"name": "Rivalitas antarsekolah", "platforms": {"x": 0.4, "instagram": 0.4, "tiktok": 0.2}, "n": 22, "cats": {"K02": 0.6, "K05": 0.4}, "harm": 0.7},
    "G2": {"name": "Promosi judi & penipuan", "platforms": {"x": 0.6, "instagram": 0.4}, "n": 16, "cats": {"K06": 1.0}, "harm": 0.95},
    "G3": {"name": "Gaya hidup nongkrong", "platforms": {"tiktok": 0.5, "instagram": 0.5}, "n": 18, "cats": {"K07": 0.8, "K04": 0.2}, "harm": 0.65},
    "G4": {"name": "Advokasi & edukasi", "platforms": {"tiktok": 0.3, "instagram": 0.3, "x": 0.2, "youtube": 0.2}, "n": 20, "cats": {"K01": 0.3, "K02": 0.15, "K03": 0.15, "K06": 0.15, "K08": 0.15, "K04": 0.1}, "harm": 0.0},
    "G5": {"name": "Media & berita", "platforms": {"youtube": 0.5, "x": 0.5}, "n": 12, "cats": {"K02": 0.25, "K03": 0.2, "K06": 0.2, "K07": 0.15, "K05": 0.2}, "harm": 0.0},
    "G6": {"name": "Debat identitas", "platforms": {"x": 0.8, "youtube": 0.2}, "n": 20, "cats": {"K08": 0.7, "K04": 0.3}, "harm": 0.6},
}

PLACES = ["Jalan Melati", "Taman Kota", "Stadion Lama", "Pasar Baru", "Terminal Timur", "Lapangan Merdeka"]
TAGS = ["#fyp", "#viral", "#trending", "#xyzbca", "#foryou", ""]

HARMFUL: dict[str, list[str]] = {
    "K01": ["wkwk liat cara jalan dia, ketawain bareng yuk {tag}", "ngatain temen sekelas budek terus, lucu banget reaksinya wkwk",
            "body shaming dikit gapapa lah {tag}", "ejek aja yang culun itu biar kapok wkwk", "si itu dibully lagi di kelas, ngakak {tag}"],
    "K02": ["malam ini tawuran di {place}, yang berani gas", "labrak aja anak sekolah sebelah, hajar sampe kapok",
            "yang ngatain sekolah kita, kita keroyok pulang sekolah", "duel satu lawan satu di {place}, jangan cupu"],
    "K03": ["challenge berbahaya: hadang truk di jalan raya, berani gak? {tag}", "ikut tren lompat dari jembatan, nekat parah {tag}",
            "tantangan tahan napas paling lama, berani gak lo {tag}"],
    "K04": ["spill foto pribadi mantan, sebar foto aja biar malu", "ini alamat rumah sama nomor hp dia, serbu rame-rame",
            "rekam diam-diam temen ganti baju wkwk {tag}"],
    "K05": ["corat-coret halte pake pilox, seru bro {tag}", "habis bolos kita merusak fasilitas umum dikit wkwk",
            "coret tembok sekolah sebelah biar tau rasa"],
    "K06": ["slot gacor hari ini, deposit 10rb auto maxwin, link di bio", "scatter turun terus bosku, judol paling gacor {tag}",
            "pinjol cepat cair tanpa ribet, auto cuan hari ini", "togel jitu malam ini, deposit receh auto maxwin"],
    "K07": ["malming nongkrong, miras oplosan biar asik {tag}", "vape rasa baru, anak sekolah wajib coba {tag}",
            "mabuk dikit gapapa, oplosan racikan sendiri"],
    "K08": ["kaum mereka sesat, usir mereka dari kampung", "benci banget sama suku itu, bukan pribumi",
            "antek asing semua, kaum mereka gak usah dikasih tempat"],
}
COUNTER: dict[str, list[str]] = {
    "K01": ["ini gak lucu. jangan ketawain disabilitas orang, hargai sesama", "stop bully, itu bukan candaan. tolong hargai temanmu"],
    "K02": ["stop tawuran, gak ada gunanya. laporkan kalau ada ajakan", "jangan mau diajak duel, hentikan kekerasan"],
    "K03": ["jangan ikut challenge hadang truk, nyawa taruhannya", "stop ikut tantangan nekat begini, gak pantas ditiru"],
    "K04": ["jangan sebar foto orang tanpa izin, itu pelecehan", "doxing itu tidak pantas, laporkan akunnya"],
    "K05": ["vandal itu bukan keren, jangan rusak fasilitas umum", "miris liat halte dicoret pilox, hentikan"],
    "K06": ["hati-hati judol, jangan tergiur maxwin. laporkan akun promosi slot", "stop promosi pinjol ilegal, banyak korban"],
    "K07": ["jangan normalisasi miras oplosan, banyak korban", "stop jualan vape ke anak sekolah, gak pantas"],
    "K08": ["intoleran itu bukan ajaran kita, hormati perbedaan", "jangan benci suku lain, kita semua saudara"],
}
EDU: dict[str, list[str]] = {
    "K01": ["edukasi: kenapa body shaming dan bully berdampak panjang. faktanya korban bisa trauma"],
    "K02": ["psikolog jelaskan dampaknya intimidasi dan tawuran pada remaja, thread edukasi"],
    "K03": ["kenapa ini berbahaya: tantangan hadang truk sudah memakan korban. edukasi keselamatan"],
    "K04": ["tips lindungi data: doxing dan sebar foto pribadi itu pelanggaran privasi"],
    "K05": ["edukasi: corat-coret fasilitas umum merugikan semua warga, faktanya biaya perbaikan besar"],
    "K06": ["edukasi: modus giveaway palsu dan judol yang menyasar pelajar, perlu kamu tahu"],
    "K07": ["faktanya vape dan miras oplosan berbahaya untuk remaja, edukasi kesehatan"],
    "K08": ["thread edukasi: kenapa ujaran benci ke suku dan agama lain merusak persatuan"],
}
NEWS: dict[str, list[str]] = {
    "K02": ["berita: polisi mengamankan pelajar yang hendak tawuran di {place}, menurut keterangan kepolisian"],
    "K03": ["berita: remaja terluka saat ikut tantangan stop truk, kronologi kejadian"],
    "K05": ["liputan: pihak sekolah dikonfirmasi memperbaiki tembok yang dicorat-coret pilox"],
    "K06": ["berita: kepolisian blokir ribuan situs judol yang menyasar pelajar"],
    "K07": ["berita: polisi razia miras oplosan di {place}, belasan remaja diamankan"],
    "K01": ["berita: pihak sekolah dikonfirmasi menindaklanjuti kasus bully siswa yang viral"],
    "K04": ["berita: kasus sebar foto pribadi pelajar dilaporkan ke polisi"],
    "K08": ["liputan: tokoh masyarakat ajak warga tolak ujaran benci antarsuku"],
}
NEUTRAL = ["jalan-jalan sore sama teman, cuaca cerah {tag}", "review jajanan kantin sekolah, enak dan murah",
           "latihan futsal buat turnamen minggu depan", "belajar bareng buat ujian, semangat", "konser musik di taman kota rame banget",
           "rekomendasi buku buat liburan", "main game bareng tim sampai malam"]
SUPPORT_REPLIES = ["wkwk ngakak parah", "gas lah", "mantap bro", "lanjutkan wkwk", "ikut dong"]

INTERACTION_TYPES = {
    "tiktok": [("komentar", 0.55), ("bagikan", 0.2), ("remix", 0.15), ("sebutan", 0.1)],
    "instagram": [("komentar", 0.6), ("sebutan", 0.2), ("bagikan", 0.2)],
    "youtube": [("komentar", 0.8), ("balasan", 0.2)],
    "x": [("balasan", 0.4), ("bagikan", 0.25), ("kutipan", 0.2), ("sebutan", 0.15)],
}
RESPONSE_TYPE = {"komentar": "komentar", "balasan": "balasan", "kutipan": "kutipan", "remix": "remix"}
REL_FOR_TYPE = {"komentar": "balasan_dari", "balasan": "balasan_dari", "kutipan": "kutipan_dari", "remix": "remix_dari", "bagikan": "repost_dari"}
MAIN_TYPE = {"tiktok": "video", "youtube": "video", "instagram": "posting", "x": "posting"}
BUCKETS = ["<1rb", "1rb–10rb", "10rb–100rb", ">100rb"]


def _pick(rng: random.Random, weights: dict[str, float]) -> str:
    r, acc = rng.random() * sum(weights.values()), 0.0
    for k, w in weights.items():
        acc += w
        if r <= acc:
            return k
    return next(iter(weights))


def _pick_pairs(rng: random.Random, pairs: list[tuple[str, float]]) -> str:
    return _pick(rng, dict(pairs))


def _fill(rng: random.Random, tpl: str) -> str:
    return tpl.format(tag=rng.choice(TAGS), place=rng.choice(PLACES)).strip()


def _metrics(rng: random.Random, platform: str, scale: float = 1.0) -> dict[str, int]:
    views = int(math.exp(rng.gauss(7.5, 1.4)) * scale)
    return {"tayangan": views if platform in ("tiktok", "youtube", "instagram") else 0,
            "suka": int(views * rng.uniform(0.02, 0.12)), "komentar": int(views * rng.uniform(0.002, 0.02)),
            "bagikan": int(views * rng.uniform(0.001, 0.01))}


def generate() -> SDataset:
    rng = random.Random(SEED)
    ds = SDataset()
    actors_by_group: dict[str, list[SActor]] = {g: [] for g in GROUPS}
    counter = 0

    # ---------------------------------------------------------------- latar: aktor
    for gid, g in GROUPS.items():
        for _ in range(g["n"]):
            counter += 1
            plat = _pick(rng, g["platforms"])
            cat = "individu"
            if gid == "G4":
                cat = rng.choice(["organisasi", "lembaga_pendidikan", "kreator", "individu"])
            elif gid == "G5":
                cat = "media"
            elif rng.random() < 0.12:
                cat = "kreator"
            bucket = BUCKETS[min(3, int(abs(rng.gauss(1.2 if cat in ("media", "kreator") else 0.7, 0.9))))]
            a = SActor(f"demo_{gid.lower()}_{plat}_{counter:03d}", plat, gid, cat, bucket)
            actors_by_group[gid].append(a)
            ds.actors.append(a)
    actor_map = {a.key: a for a in ds.actors}

    # ---------------------------------------------------------------- latar: konten asli
    span = (PERIOD_END - PERIOD_START).total_seconds()
    originals: list[SContent] = []
    n_content = 0
    for a in ds.actors:
        g = GROUPS[a.group]
        for _ in range(rng.randint(1, 4)):
            n_content += 1
            t = PERIOD_START + timedelta(seconds=rng.random() * span)
            if rng.random() < 0.18:
                text = _fill(rng, rng.choice(NEUTRAL))
            else:
                cat = _pick(rng, g["cats"])
                if a.group == "G5":
                    text = _fill(rng, rng.choice(NEWS.get(cat, NEWS["K02"])))
                elif a.group == "G4":
                    text = _fill(rng, rng.choice(EDU[cat] + COUNTER[cat]))
                elif rng.random() < g["harm"]:
                    text = _fill(rng, rng.choice(HARMFUL[cat]))
                else:
                    text = _fill(rng, rng.choice(COUNTER[cat]))
            c = SContent(f"bg{n_content:04d}", a.key, a.platform, t, MAIN_TYPE[a.platform], text,
                         _metrics(rng, a.platform, 3 if a.account_category in ("media", "kreator") else 1),
                         has_media=a.platform in ("tiktok", "youtube", "instagram"))
            originals.append(c)
    ds.contents.extend(originals)

    # ---------------------------------------------------------------- latar: interaksi & respons
    platform_actors: dict[str, list[SActor]] = {}
    for a in ds.actors:
        platform_actors.setdefault(a.platform, []).append(a)
    n_resp = 0
    for c in originals:
        author = actor_map[c.actor]
        n_inter = min(14, int(rng.expovariate(1 / 3.2)) + (2 if author.account_category in ("media", "kreator") else 0))
        same_group = [x for x in actors_by_group[author.group] if x.platform == c.platform and x.key != author.key]
        others = [x for x in platform_actors[c.platform] if x.key != author.key]
        for _ in range(n_inter):
            pool = same_group if same_group and rng.random() < 0.72 else others
            if not pool:
                continue
            responder = rng.choice(pool)
            itype = _pick_pairs(rng, INTERACTION_TYPES[c.platform])
            t = c.published_at + timedelta(hours=rng.expovariate(1 / 18))
            if t > PERIOD_END:
                continue
            response_key = None
            if itype in RESPONSE_TYPE and rng.random() < 0.35:
                n_resp += 1
                r_text = _response_text(rng, responder, c)
                rc = SContent(f"rs{n_resp:04d}", responder.key, c.platform, t, RESPONSE_TYPE[itype], r_text,
                              _metrics(rng, c.platform, 0.05), has_media=itype == "remix")
                ds.contents.append(rc)
                response_key = rc.key
                ds.relations.append(SRelation(c.key, rc.key, REL_FOR_TYPE[itype], "atribusi_terkonfirmasi", True,
                                              [{"evidence_type": "metadata_platform", "direction": "mendukung", "strength": 1.0,
                                                "description": f"Relasi '{itype}' tercatat pada metadata platform."}]))
            ds.interactions.append(SInteraction(responder.key, author.key, c.key, response_key, itype, t, c.platform))

    # beberapa "sebutan" lintas kelompok oleh akun advokasi & media (jembatan antar-komunitas)
    for a in actors_by_group["G4"] + actors_by_group["G5"]:
        for _ in range(rng.randint(1, 3)):
            target = rng.choice([x for x in platform_actors[a.platform] if x.key != a.key])
            ds.interactions.append(SInteraction(a.key, target.key, None, None, "sebutan",
                                                PERIOD_START + timedelta(seconds=rng.random() * span), a.platform))

    _scenario_ableism(ds)
    _scenario_challenge(ds)
    _scenario_gambling(ds, actors_by_group["G2"])
    return ds


def _response_text(rng: random.Random, responder: SActor, c: SContent) -> str:
    if responder.group in ("G4", "G5"):
        for cat, tpls in HARMFUL.items():
            if any(tpl.split(" ")[0] in c.text for tpl in tpls):
                return _fill(rng, rng.choice(COUNTER[cat]))
        return _fill(rng, rng.choice(COUNTER["K01"]))
    if GROUPS[responder.group]["harm"] > 0.5 and rng.random() < 0.7:
        return rng.choice(SUPPORT_REPLIES)
    return _fill(rng, rng.choice(NEUTRAL))


def _t(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=WIB)


def _ev(etype: str, direction: str, strength: float, desc: str) -> dict[str, Any]:
    return {"evidence_type": etype, "direction": direction, "strength": strength, "description": desc}


# ---------------------------------------------------------------------------- ABL-01

def _scenario_ableism(ds: SDataset) -> None:
    sc = "ABL-01"
    A = {
        "x_awal": ("x", "G6", "individu", "<1rb"), "tt_pembuat": ("tiktok", "G0", "individu", "10rb–100rb"),
        "tt_duet1": ("tiktok", "G0", "individu", "1rb–10rb"), "tt_duet2": ("tiktok", "G0", "individu", "<1rb"),
        "ig_reels": ("instagram", "G0", "individu", "1rb–10rb"), "x_kritik": ("x", "G4", "individu", "1rb–10rb"),
        "yt_kompilasi": ("youtube", "G0", "kreator", "10rb–100rb"), "tt_advokasi": ("tiktok", "G4", "organisasi", "10rb–100rb"),
        "yt_media": ("youtube", "G5", "media", ">100rb"), "tt_lanjut1": ("tiktok", "G0", "individu", "<1rb"),
        "ig_lanjut2": ("instagram", "G0", "individu", "1rb–10rb"), "tt_lanjut3": ("tiktok", "G0", "individu", "1rb–10rb"),
        "ig_sekolah": ("instagram", "G4", "lembaga_pendidikan", "1rb–10rb"), "x_satire": ("x", "G6", "kreator", "1rb–10rb"),
    }
    for k, (p, g, cat, b) in A.items():
        ds.actors.append(SActor(f"demo_abl_{k}", p, g, cat, b))

    def C(key, actor, plat, t, ctype, text, views, media=True):
        c = SContent(key, f"demo_abl_{actor}", plat, _t(t), ctype, text,
                     {"tayangan": views, "suka": views // 12, "komentar": views // 90, "bagikan": views // 160},
                     has_media=media, scenario=sc, code=f"ABL-{key}")
        ds.contents.append(c)
        return c

    C("C00", "ig_lanjut2", "instagram", "2026-06-28T16:40", "video", "gaya jalan aneh ala gue wkwk", 900)
    C("C0", "x_awal", "x", "2026-07-12T20:05", "posting", "gaya jalan temen gue pagi ini kayak robot rusak wkwk", 0, media=False)
    C("C1", "tt_pembuat", "tiktok", "2026-07-14T19:20", "video",
      "meniru gaya jalan orang pincang biar viral wkwk, ketawain bareng #gayajalanchallenge", 184000)
    C("C2", "tt_duet1", "tiktok", "2026-07-15T10:12", "remix", "duet: gaya jalan versi gue wkwk #gayajalanchallenge", 22000)
    C("C3", "tt_duet2", "tiktok", "2026-07-15T21:40", "remix", "stitch: ikut meniru, ketawain aja #gayajalanchallenge", 8400)
    C("C5", "x_kritik", "x", "2026-07-16T08:15", "kutipan",
      "ini gak lucu. meniru gaya jalan penyandang disabilitas itu merendahkan. stop ketawain disabilitas", 0, media=False)
    C("C4", "ig_reels", "instagram", "2026-07-16T18:30", "video", "meniru gaya jalan viral wkwk #gayajalanchallenge", 15600)
    C("C7", "tt_advokasi", "tiktok", "2026-07-17T12:00", "remix",
      "edukasi: kenapa meniru gaya jalan penyandang disabilitas itu menyakitkan. hargai, jangan jadikan candaan", 61000)
    C("C6", "yt_kompilasi", "youtube", "2026-07-18T17:45", "video",
      "kompilasi gaya jalan lucu viral minggu ini wkwk (sumber: TikTok)", 47000)
    C("C13", "x_satire", "x", "2026-07-19T09:30", "kutipan",
      "parodi: kalau para pembully gaya jalan bikin podcast, isinya cuma ejek doang", 0, media=False)
    C("C8", "yt_media", "youtube", "2026-07-20T18:00", "video",
      "berita: tren meniru gaya jalan disabilitas viral di media sosial, pihak sekolah dan pegiat disabilitas angkat bicara", 126000)
    C("C9", "tt_lanjut1", "tiktok", "2026-07-25T20:10", "video", "gaya jalan baru wkwk siapa yang bisa niru", 3100)
    C("C10", "ig_lanjut2", "instagram", "2026-07-28T15:00", "video", "meniru gaya jalan lagi wkwk", 2200)
    C("C11", "tt_lanjut3", "tiktok", "2026-08-02T19:45", "video", "#gayajalanchallenge part 2 wkwk, ketawain bareng", 9800)
    C("C12", "ig_sekolah", "instagram", "2026-08-05T08:00", "posting",
      "kampanye #HormatiPerbedaan: stop bully dan ejek disabilitas, sekolah ramah untuk semua", 5400)

    R = ds.relations.append
    meta = lambda d: _ev("metadata_platform", "mendukung", 1.0, d)  # noqa: E731
    R(SRelation("C1", "C2", "remix_dari", "atribusi_terkonfirmasi", True, [meta("Duet TikTok merujuk video C1 (metadata duet).")]))
    R(SRelation("C1", "C3", "remix_dari", "atribusi_terkonfirmasi", True, [meta("Stitch TikTok merujuk video C1 (metadata stitch).")]))
    R(SRelation("C1", "C7", "remix_dari", "atribusi_terkonfirmasi", True, [meta("Stitch edukatif oleh akun advokasi merujuk C1.")]))
    R(SRelation("C1", "C5", "lintas_platform", "atribusi_terkonfirmasi", False, [
        _ev("atribusi_eksplisit", "mendukung", 0.9, "Posting X memuat tangkapan layar video C1 dengan nama akun & watermark terlihat."),
        _ev("urutan_waktu", "mendukung", 0.4, "Terbit ±37 jam setelah C1.")]))
    R(SRelation("C1", "C6", "lintas_platform", "atribusi_terkonfirmasi", False, [
        _ev("atribusi_eksplisit", "mendukung", 0.9, "Deskripsi video mencantumkan kredit sumber TikTok yang cocok dengan C1."),
        _ev("kemiripan_visual", "mendukung", 0.7, "Potongan video C1 muncul di detik 00:12–00:31 (dicatat peninjau).")]))
    R(SRelation("C1", "C8", "lintas_platform", "atribusi_terkonfirmasi", False, [
        _ev("atribusi_eksplisit", "mendukung", 0.9, "Segmen berita menampilkan dan menyebut video C1 sebagai contoh tren.")]))
    R(SRelation("C1", "C4", "lintas_platform", "replikasi_didukung", False, [
        _ev("kemiripan_teks", "mendukung", 0.6, "Teks dan tagar sangat mirip dengan C1."),
        _ev("audio_sama", "mendukung", 0.8, "Memakai audio 'suara asli – DEMO-112' yang sama dengan C1."),
        _ev("tagar_tren", "mendukung", 0.6, "Memakai tagar #gayajalanchallenge yang pertama teramati pada C1."),
        _ev("urutan_waktu", "mendukung", 0.4, "Terbit ±47 jam setelah C1."),
        _ev("celah_data", "netral", 0.3, "Tidak ada tautan eksplisit; akun IG tidak menyebut sumber.")]))
    R(SRelation("C5", "C13", "kutipan_dari", "atribusi_terkonfirmasi", True, [meta("Quote-post X atas C5 (referenced_tweets).")]))
    R(SRelation("C8", "C12", "lintas_platform", "atribusi_terkonfirmasi", False, [
        _ev("atribusi_eksplisit", "mendukung", 0.8, "Keterangan kampanye mengutip liputan C8.")]))
    R(SRelation("C1", "C9", "kemiripan", "kemungkinan_replikasi", False, [
        _ev("kemiripan_teks", "mendukung", 0.4, "Frasa 'gaya jalan' & penanda tawa mirip."),
        _ev("kemiripan_visual", "mendukung", 0.5, "Gestur serupa (dicatat peninjau, tanpa analisis wajah)."),
        _ev("celah_data", "netral", 0.3, "Tidak ada audio/tagar yang sama; tidak ada rujukan eksplisit.")]))
    R(SRelation("C1", "C10", "kemiripan", "kemungkinan_replikasi", False, [
        _ev("kemiripan_teks", "mendukung", 0.5, "Teks mirip dengan C1 dan C4."),
        _ev("kemiripan_visual", "mendukung", 0.5, "Gestur serupa dengan C1."),
        _ev("perilaku_sebelumnya", "bertentangan", 0.7, "Akun yang sama sudah memuat gestur serupa pada C00 (28 Juni), "
            "SEBELUM C1 terbit — peniruan dari C1 tidak dapat disimpulkan.")],
        notes="Contoh bukti bertentangan: perilaku mendahului konten yang diduga ditiru."))
    R(SRelation("C1", "C11", "lintas_platform", "replikasi_didukung", False, [
        _ev("tagar_tren", "mendukung", 0.7, "Memakai #gayajalanchallenge dan menyebut 'part 2'."),
        _ev("audio_sama", "mendukung", 0.8, "Audio identik dengan C1."),
        _ev("kemiripan_teks", "mendukung", 0.5, "Frasa 'ketawain bareng' sama dengan C1.")]))
    R(SRelation("C00", "C10", "kemiripan", "kemiripan", False, [
        _ev("kemiripan_teks", "mendukung", 0.5, "Akun sama, teks mirip."),
        _ev("catatan_peneliti", "netral", 0.2, "Relasi kemiripan internal akun — bukan bukti transmisi.")]))
    R(SRelation("C0", "C1", "kemiripan", "kemiripan", False, [
        _ev("kemiripan_teks", "mendukung", 0.35, "Sama-sama menyebut 'gaya jalan' dan penanda tawa."),
        _ev("catatan_peneliti", "bertentangan", 0.6, "Konteks berbeda: C0 tentang teman sendiri, tidak menyasar disabilitas; "
            "tidak ada indikasi akun TikTok melihat C0.")]))

    # interaksi di sekitar video C1 (komentar mendukung & kontra-narasi) + duet
    comments = [("tt_duet1", "remix", "C1"), ("tt_duet2", "remix", "C1"), ("tt_advokasi", "remix", "C1"), ("tt_lanjut1", "komentar", "C1"),
                ("tt_lanjut3", "komentar", "C1"), ("tt_lanjut3", "bagikan", "C1"), ("tt_advokasi", "komentar", "C2"),
                ("tt_lanjut1", "komentar", "C2"), ("tt_pembuat", "komentar", "C7"), ("tt_duet1", "bagikan", "C1"),
                ("ig_lanjut2", "komentar", "C4"), ("ig_sekolah", "komentar", "C4"), ("x_satire", "kutipan", "C5"),
                ("x_awal", "balasan", "C5"), ("yt_media", "komentar", "C6")]
    by_key = {c.key: c for c in ds.contents if c.scenario == sc}
    for i, (actor, itype, ckey) in enumerate(comments):
        c = by_key[ckey]
        ds.interactions.append(SInteraction(f"demo_abl_{actor}", c.actor, c.key, None, itype,
                                            c.published_at + timedelta(hours=2 + i * 1.5), c.platform))
    # pengikut pasif ikut berkomentar di C1 (aktor latar G0 TikTok)
    bg_tt = [a for a in ds.actors if a.group == "G0" and a.platform == "tiktok" and not a.key.startswith("demo_abl")][:10]
    texts = ["wkwk ngakak parah", "gak lucu, hapus aja", "laporkan aja ini, tidak pantas", "wkwk ikut dong", "miris banget liatnya"]
    for i, a in enumerate(bg_tt):
        t = by_key["C1"].published_at + timedelta(hours=1 + i * 3)
        key = f"ABL-K{i + 1:02d}"
        rc = SContent(key, a.key, "tiktok", t, "komentar", texts[i % len(texts)], {"suka": 12 * (i + 1)}, scenario=sc, code=key)
        ds.contents.append(rc)
        ds.interactions.append(SInteraction(a.key, by_key["C1"].actor, "C1", key, "komentar", t, "tiktok"))
        ds.relations.append(SRelation("C1", key, "balasan_dari", "atribusi_terkonfirmasi", True,
                                      [meta("Komentar tercatat pada metadata video C1.")]))
    ds.content_evidence.append({"content": "C1", **_ev("celah_data", "netral", 0.5,
                               "Hanya ±30% komentar C1 terkumpul (batas kuota API pada periode pengumpulan).")})
    ds.content_evidence.append({"content": "C1", **_ev("catatan_peneliti", "netral", 0.3,
                               "C1 adalah konten paling viral, BUKAN konten pertama yang teramati (lihat C00 dan C0).")})


# ---------------------------------------------------------------------------- TTG-01

def _scenario_challenge(ds: SDataset) -> None:
    sc = "TTG-01"
    for k, (p, g, cat) in {"tt_awal": ("tiktok", "G0", "kreator"), "tt_ikut1": ("tiktok", "G0", "individu"),
                           "tt_ikut2": ("tiktok", "G0", "individu"), "yt_komp": ("youtube", "G0", "kreator"),
                           "ig_ikut": ("instagram", "G0", "individu"), "x_media": ("x", "G5", "media"),
                           "tt_edu": ("tiktok", "G4", "organisasi")}.items():
        ds.actors.append(SActor(f"demo_ttg_{k}", p, g, cat, "1rb–10rb"))

    def C(key, actor, plat, t, ctype, text, views):
        ds.contents.append(SContent(key, f"demo_ttg_{actor}", plat, _t(t), ctype, text,
                                    {"tayangan": views, "suka": views // 10, "komentar": views // 80, "bagikan": views // 120},
                                    has_media=plat != "x", scenario=sc, code=f"TTG-{key}"))

    C("H1", "tt_awal", "tiktok", "2026-08-10T21:00", "video", "challenge berbahaya hadang truk, berani gak? #stoptrukchallenge", 96000)
    C("H2", "tt_ikut1", "tiktok", "2026-08-11T20:30", "remix", "duet: gue juga berani hadang truk #stoptrukchallenge", 12000)
    C("H3", "tt_ikut2", "tiktok", "2026-08-12T19:10", "remix", "stitch: nekat parah hadang truk bareng temen #stoptrukchallenge", 7000)
    C("H4", "yt_komp", "youtube", "2026-08-13T18:00", "video", "kompilasi challenge hadang truk paling nekat (sumber: TikTok)", 54000)
    C("H5", "ig_ikut", "instagram", "2026-08-14T17:20", "video", "hadang truk challenge versi kita, berani gak #stoptrukchallenge", 6400)
    C("H6", "x_media", "x", "2026-08-15T07:00", "posting",
      "berita: polisi imbau orang tua awasi tren tantangan hadang truk, kronologi remaja terluka", 0)
    C("H7", "tt_edu", "tiktok", "2026-08-16T12:00", "remix", "kenapa ini berbahaya: jangan ikut challenge hadang truk, nyawa taruhannya", 41000)
    meta = lambda d: _ev("metadata_platform", "mendukung", 1.0, d)  # noqa: E731
    for a, b, rel, st, doc, ev in [
        ("H1", "H2", "remix_dari", "atribusi_terkonfirmasi", True, [meta("Duet merujuk H1.")]),
        ("H1", "H3", "remix_dari", "atribusi_terkonfirmasi", True, [meta("Stitch merujuk H1.")]),
        ("H1", "H7", "remix_dari", "atribusi_terkonfirmasi", True, [meta("Stitch edukatif merujuk H1.")]),
        ("H1", "H4", "lintas_platform", "atribusi_terkonfirmasi", False, [_ev("atribusi_eksplisit", "mendukung", 0.9, "Kredit sumber TikTok di deskripsi.")]),
        ("H1", "H5", "lintas_platform", "replikasi_didukung", False, [_ev("audio_sama", "mendukung", 0.7, "Audio sama dengan H1."),
                                                                         _ev("tagar_tren", "mendukung", 0.7, "Tagar #stoptrukchallenge.")]),
        ("H4", "H6", "lintas_platform", "atribusi_terkonfirmasi", False, [_ev("atribusi_eksplisit", "mendukung", 0.8, "Posting menautkan video H4.")]),
    ]:
        ds.relations.append(SRelation(a, b, rel, st, doc, ev))
    for actor, itype, ckey, h in [("tt_ikut1", "remix", "H1", 23), ("tt_ikut2", "remix", "H1", 46), ("tt_edu", "remix", "H1", 135),
                                  ("tt_ikut1", "komentar", "H3", 50), ("tt_edu", "komentar", "H2", 60)]:
        target = next(c for c in ds.contents if c.key == ckey)
        ds.interactions.append(SInteraction(f"demo_ttg_{actor}", target.actor, ckey, None, itype,
                                            _t("2026-08-10T21:00") + timedelta(hours=h), "tiktok"))


# ---------------------------------------------------------------------------- JDL-01

def _scenario_gambling(ds: SDataset, g2: list[SActor]) -> None:
    sc = "JDL-01"
    rng = random.Random(SEED + 6)
    accounts = g2[:6]
    base = _t("2026-09-01T19:00")
    variants = ["slot gacor malam ini, deposit 10rb auto maxwin, link di bio", "slot gacor malam ini!! depo 10rb auto maxwin link di bio",
                "sl0t gacor malam ini, deposit 10rb auto maxwin, cek link di bio", "slot gacoor malam ini deposit 10rb auto maxwinn link di bio",
                "malam ini slot gacor, deposit 10rb langsung maxwin, link di bio", "slot gacor malam ini, deposit 10rb auto maxwin, link di bio bosku"]
    keys = []
    for i, (a, txt) in enumerate(zip(accounts, variants)):
        key = f"J{i + 1}"
        keys.append(key)
        ds.contents.append(SContent(key, a.key, a.platform, base + timedelta(hours=i * 9 + rng.random() * 3), "posting", txt,
                                    {"tayangan": 0, "suka": rng.randint(2, 40), "komentar": rng.randint(0, 5), "bagikan": rng.randint(0, 9)},
                                    scenario=sc, code=f"JDL-{key}"))
    for i in range(1, len(keys)):
        st = "kemungkinan_replikasi" if i % 2 == 0 else "kemiripan"
        ev = [_ev("kemiripan_teks", "mendukung", 0.8, "Teks hampir identik (salin-tempel dengan variasi ejaan).")]
        if st == "kemungkinan_replikasi":
            ev.append(_ev("tagar_tren", "mendukung", 0.5, "Pola 'link di bio' & nominal deposit sama."))
        ev.append(_ev("catatan_peneliti", "netral", 0.4, "Bisa berasal dari templat iklan bersama — arah peniruan tidak dapat ditentukan."))
        ds.relations.append(SRelation(keys[0], keys[i], "kemiripan", st, False, ev))
