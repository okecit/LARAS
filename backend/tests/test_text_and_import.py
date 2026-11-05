"""Uji normalisasi, klasifikasi kontekstual, kemiripan, pseudonimisasi, dan validasi impor."""
from datetime import timezone

from app.classifier import RuleClassifier, discover_keywords
from app.connectors import parse_timestamp
from app.connectors.platforms import XConnector
from app.ingest import parse_import_file
from app.security import actor_hash, hash_password, pseudonym_for, verify_password
from app.taxonomy import CATEGORIES
from app.textproc import normalize, similarity

CLF = RuleClassifier(CATEGORIES)


def labels(text):
    return {l.code: l for l in CLF.classify(text).labels}


def test_normalize_slang_leet_repeats():
    assert normalize("Gk lucu bgttt @budi https://x.co/a") == "gak lucu banget @user <url>"
    assert normalize("sl0t gac0r") == "slot gacor"
    assert normalize("#StopBullying") == "stopbullying"


def test_harmful_candidate_detected():
    res = CLF.classify("slot gacor hari ini, deposit 10rb auto maxwin, link di bio")
    assert res.context_label == "kandidat_berbahaya"
    assert res.labels[0].code == "K06" and res.labels[0].confidence > 0.8


def test_counter_speech_is_not_harmful():
    res = CLF.classify("ini gak lucu. jangan ketawain disabilitas orang, hargai sesama")
    assert res.context_label == "kontra_narasi"
    k01 = labels("ini gak lucu. jangan ketawain disabilitas orang, hargai sesama")["K01"]
    assert k01.context_label == "kontra_narasi" and k01.confidence < 0.4


def test_news_and_education_contexts():
    assert CLF.classify("berita: polisi mengamankan pelajar yang hendak tawuran, menurut keterangan kepolisian").context_label == "berita"
    assert CLF.classify("edukasi: kenapa meniru gaya jalan penyandang disabilitas itu menyakitkan. jangan").context_label == "edukasi"


def test_multilabel():
    found = labels("ejek si culun lalu ajak tawuran di taman, hajar")
    assert {"K01", "K02"} <= set(found)


def test_neutral_text_has_no_labels():
    res = CLF.classify("belajar bareng buat ujian, semangat")
    assert res.labels == [] and res.context_label == "netral"


def test_similarity_is_spelling_robust():
    a = "slot gacor malam ini, deposit 10rb auto maxwin, link di bio"
    assert similarity(a, "sl0t gacoor malam ini deposit 10rb auto maxwinn link di bio") > 0.75
    assert similarity(a, "belajar bareng buat ujian") < 0.2


def test_keyword_discovery_excludes_existing_terms():
    sugg = discover_keywords({"K06": ["slot gacor bosku", "judol gacor bosku", "bosku maxwin"]},
                             ["slot gacor bosku", "judol gacor bosku", "bosku maxwin", "makan siang", "belajar"],
                             {"K06": {"gacor"}})
    terms = [s["term"] for s in sugg["K06"]]
    assert "bosku" in terms and "gacor" not in terms


def test_pseudonym_is_stable_and_irreversible():
    h1 = actor_hash("tiktok", "@Akun_Contoh", key="k")
    assert h1 == actor_hash("tiktok", "akun_contoh", key="k")
    assert h1 != actor_hash("x", "akun_contoh", key="k")
    assert "akun" not in pseudonym_for("tiktok", h1).lower()
    assert pseudonym_for("tiktok", h1).startswith("TT-")


def test_password_hashing():
    h = hash_password("rahasia-panjang")
    assert verify_password("rahasia-panjang", h) and not verify_password("salah", h)


def test_timestamp_normalised_to_utc():
    assert parse_timestamp("2026-07-14T19:20:00+07:00").hour == 12
    assert parse_timestamp("2026-07-14 12:00:00").tzinfo == timezone.utc
    assert parse_timestamp(0).year == 1970


CSV = (b"platform,external_id,author_handle,published_at,text,content_type,parent_external_id,interaction_type\n"
       b"x,1,akun_a,2026-07-14T19:20:00+07:00,posting awal,posting,,\n"
       b"x,2,akun_b,2026-07-14T21:00:00+07:00,balasan,balasan,1,balasan\n"
       b"x,2,akun_b,2026-07-14T21:00:00+07:00,duplikat,balasan,1,balasan\n"
       b"facebook,3,akun_c,kemarin,teks,posting,,\n"
       b"x,4,,2026-07-15T00:00:00Z,tanpa penulis,posting,,\n"
       b"x,5,akun_d,2026-07-15T00:00:00Z,komentar tanpa induk,komentar,,komentar\n")


def test_import_validation_report():
    rep = parse_import_file("data.csv", CSV)
    assert rep.total_rows == 6
    assert len(rep.valid) == 2
    assert rep.duplicates_in_file == 1
    fields = {(e["row"], e["field"]) for e in rep.errors}
    assert (4, "platform") in fields and (4, "published_at") in fields
    assert (5, "author_handle") in fields
    assert (6, "parent_external_id") in fields
    reply = rep.valid[1]
    assert reply.relation_type == "balasan_dari" and reply.parent_external_id == "1"


def test_import_json():
    rep = parse_import_file("d.json", b'{"items": [{"platform": "youtube", "external_id": "v1", "author_handle": "ch", '
                                       b'"published_at": 1784000000, "text": "halo", "content_type": "video"}]}')
    assert len(rep.valid) == 1 and rep.valid[0].published_at.tzinfo == timezone.utc


def test_x_response_normalisation():
    data = {"data": [{"id": "9", "author_id": "u2", "created_at": "2026-07-16T01:15:00.000Z", "text": "ini gak lucu",
                      "referenced_tweets": [{"type": "quoted", "id": "8"}], "public_metrics": {"like_count": 3, "retweet_count": 1,
                                                                                              "quote_count": 0, "reply_count": 0}}],
            "includes": {"tweets": [{"id": "8", "author_id": "u1"}]}}
    item = next(XConnector.normalize_response(data))
    assert item.relation_type == "kutipan_dari" and item.parent_author_handle == "u1" and item.content_type == "kutipan"
