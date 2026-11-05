"""Uji aturan bukti difusi: kemiripan tidak pernah menjadi transmisi tanpa bukti."""
from datetime import datetime, timedelta, timezone

from app.diffusion import Evidence, build_cascade, cascade_components, clamp_status, confidence_for, max_supported_status

T0 = datetime(2026, 7, 14, 12, tzinfo=timezone.utc)


def test_similarity_alone_never_upgrades():
    ev = [Evidence("kemiripan_teks", "mendukung", 0.95)]
    assert max_supported_status(ev, True) == "kemiripan"
    assert clamp_status("atribusi_terkonfirmasi", ev, True) == "kemiripan"


def test_no_evidence_is_similarity_only():
    assert max_supported_status([], True) == "kemiripan"
    assert clamp_status("replikasi_didukung", [], None) == "kemiripan"


def test_platform_metadata_confirms_attribution():
    assert max_supported_status([Evidence("metadata_platform", "mendukung", 1)], True) == "atribusi_terkonfirmasi"
    assert max_supported_status([Evidence("atribusi_eksplisit", "mendukung", 0.9)], None) == "atribusi_terkonfirmasi"


def test_reverse_chronology_blocks_replication():
    ev = [Evidence("audio_sama", "mendukung", 0.9), Evidence("tagar_tren", "mendukung", 0.9)]
    assert max_supported_status(ev, False) == "kemiripan"
    assert max_supported_status(ev, True) == "replikasi_didukung"


def test_one_independent_indicator_is_possible_replication():
    ev = [Evidence("kemiripan_teks", "mendukung", 0.6), Evidence("audio_sama", "mendukung", 0.8)]
    assert max_supported_status(ev, True) == "kemungkinan_replikasi"


def test_contradicting_evidence_downgrades():
    ev = [Evidence("audio_sama", "mendukung", 0.8), Evidence("tagar_tren", "mendukung", 0.7),
          Evidence("perilaku_sebelumnya", "bertentangan", 0.7)]
    assert max_supported_status(ev, True) == "kemungkinan_replikasi"
    ev.append(Evidence("catatan_peneliti", "bertentangan", 0.5))
    assert max_supported_status(ev, True) == "kemiripan"


def test_confidence_penalised_by_contradiction():
    assert confidence_for("replikasi_didukung", [Evidence("x", "bertentangan", 1.0)]) < confidence_for("replikasi_didukung", [])


def _items():
    return [
        {"id": "c0", "platform": "instagram", "published_at": T0 - timedelta(days=16)},
        {"id": "c1", "platform": "tiktok", "published_at": T0},
        {"id": "c2", "platform": "tiktok", "published_at": T0 + timedelta(hours=12)},
        {"id": "c3", "platform": "youtube", "published_at": T0 + timedelta(days=4)},
    ]


def test_cascade_first_observed_differs_from_transmission_root():
    rels = [
        {"source": "c1", "target": "c2", "relation_type": "remix_dari", "evidence_status": "atribusi_terkonfirmasi"},
        {"source": "c1", "target": "c3", "relation_type": "lintas_platform", "evidence_status": "atribusi_terkonfirmasi"},
        {"source": "c0", "target": "c1", "relation_type": "kemiripan", "evidence_status": "kemiripan"},
    ]
    out = build_cascade(_items(), rels)
    nodes = {n["id"]: n for n in out["nodes"]}
    assert out["summary"]["first_observed_id"] == "c0"
    assert nodes["c0"]["is_first_observed"] and not nodes["c0"]["is_transmission_root"]
    assert nodes["c1"]["is_transmission_root"]
    assert nodes["c2"]["depth"] == 1
    assert out["summary"]["transmission_relations"] == 2  # kemiripan tidak dihitung
    assert out["summary"]["originator_known"] is False
    assert any("kemiripan" in u["message"] for u in out["uncertainties"])
    assert out["summary"]["platforms_sequence"] == ["instagram", "tiktok", "youtube"]


def test_cascade_flags_unconfirmed_cross_platform():
    rels = [{"source": "c1", "target": "c3", "relation_type": "lintas_platform", "evidence_status": "kemungkinan_replikasi"}]
    out = build_cascade(_items()[1:], rels)
    assert any("lintas platform" in u["message"] for u in out["uncertainties"])


def test_cascade_components_min_size():
    comps = cascade_components([(1, 2), (2, 3), (4, 5)], min_size=3)
    assert comps == [{1, 2, 3}]
