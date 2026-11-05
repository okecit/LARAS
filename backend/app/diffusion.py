"""Analisis difusi temporal konten.

Prinsip epistemik:
- "Konten pertama yang teramati" ≠ "pencipta asli". Data yang tidak terkumpul bisa lebih awal.
- Kemiripan saja tidak pernah menjadi edge transmisi.
- Status bukti dinaikkan hanya bila syarat bukti terpenuhi (lihat `max_supported_status`).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import networkx as nx

EVIDENCE_STATUSES = ["kemiripan", "kemungkinan_replikasi", "replikasi_didukung", "atribusi_terkonfirmasi"]
EVIDENCE_LABELS = {
    "kemiripan": "Konten serupa",
    "kemungkinan_replikasi": "Kemungkinan replikasi",
    "replikasi_didukung": "Replikasi didukung bukti",
    "atribusi_terkonfirmasi": "Atribusi terkonfirmasi",
}
EVIDENCE_DESCRIPTIONS = {
    "kemiripan": "Hanya kemiripan teks/visual. Bukan bukti bahwa satu konten meniru yang lain.",
    "kemungkinan_replikasi": "Kemiripan + urutan waktu konsisten + minimal satu indikator independen lain.",
    "replikasi_didukung": "Minimal dua indikator independen (mis. audio sama, tagar tren, kemiripan visual) tanpa bukti bertentangan yang kuat.",
    "atribusi_terkonfirmasi": "Didokumentasikan platform (balasan/repost/duet/kutipan) atau atribusi eksplisit (kredit, tautan sumber).",
}

TRANSMISSION_RELATIONS = {"balasan_dari", "repost_dari", "kutipan_dari", "remix_dari", "lintas_platform"}
DOCUMENTED_EVIDENCE = {"metadata_platform", "atribusi_eksplisit"}
INDEPENDENT_INDICATORS = {"audio_sama", "kemiripan_visual", "tagar_tren", "catatan_peneliti", "kemiripan_teks"}


@dataclass
class Evidence:
    evidence_type: str
    direction: str  # mendukung|bertentangan|netral
    strength: float = 0.5


def max_supported_status(evidence: Iterable[Evidence], published_order_ok: bool | None) -> str:
    """Status bukti tertinggi yang diizinkan oleh catatan bukti yang ada.

    published_order_ok: True bila konten turunan terbit SETELAH sumber; False bila sebelum
    (maka replikasi tidak mungkin); None bila waktu tidak diketahui.
    """
    ev = list(evidence)
    supporting = [e for e in ev if e.direction == "mendukung"]
    contradicting = [e for e in ev if e.direction == "bertentangan"]
    if any(e.evidence_type in DOCUMENTED_EVIDENCE for e in supporting):
        return "atribusi_terkonfirmasi"
    if published_order_ok is False:
        return "kemiripan"
    indicators = {e.evidence_type for e in supporting if e.evidence_type in INDEPENDENT_INDICATORS}
    non_text = indicators - {"kemiripan_teks"}
    strong_contra = sum(e.strength for e in contradicting)
    if published_order_ok and len(non_text) >= 2 and strong_contra < 0.6:
        return "replikasi_didukung"
    if published_order_ok and len(indicators) >= 2 and strong_contra < 0.9:
        return "kemungkinan_replikasi"
    if published_order_ok and len(non_text) >= 1 and strong_contra < 0.9:
        return "kemungkinan_replikasi"
    return "kemiripan"


def clamp_status(requested: str, evidence: Iterable[Evidence], published_order_ok: bool | None) -> str:
    """Status yang diminta peneliti dibatasi oleh bukti — mencegah fabrikasi tautan difusi."""
    allowed = max_supported_status(evidence, published_order_ok)
    if EVIDENCE_STATUSES.index(requested) <= EVIDENCE_STATUSES.index(allowed):
        return requested
    return allowed


def confidence_for(status: str, evidence: Iterable[Evidence]) -> float:
    base = {"kemiripan": 0.2, "kemungkinan_replikasi": 0.45, "replikasi_didukung": 0.7, "atribusi_terkonfirmasi": 0.95}[status]
    ev = list(evidence)
    contra = sum(e.strength for e in ev if e.direction == "bertentangan")
    return round(max(0.05, base - 0.15 * contra), 3)


def build_cascade(items: list[dict[str, Any]], relations: list[dict[str, Any]]) -> dict[str, Any]:
    """Susun kaskade dari konten (id, published_at, platform, ...) dan relasi (source, target, evidence_status, ...).

    Mengembalikan node berurutan kronologis + kedalaman, edge, ringkasan, dan indikator ketidakpastian.
    """
    if not items:
        return {"nodes": [], "edges": [], "summary": {}, "uncertainties": []}
    by_id = {it["id"]: it for it in items}
    ordered = sorted(items, key=lambda it: it["published_at"])
    first = ordered[0]
    t0: datetime = first["published_at"]

    g = nx.DiGraph()
    g.add_nodes_from(by_id)
    for r in relations:
        if r["source"] in by_id and r["target"] in by_id:
            g.add_edge(r["source"], r["target"], **r)

    # kedalaman hanya melalui edge transmisi berbukti (bukan kemiripan)
    trans = nx.DiGraph()
    trans.add_nodes_from(by_id)
    trans.add_edges_from((u, v) for u, v, d in g.edges(data=True) if d.get("evidence_status") != "kemiripan")
    roots = [n for n in trans if trans.in_degree(n) == 0]
    depth: dict[Any, int] = {}
    for r in roots:
        for node, d in nx.single_source_shortest_path_length(trans, r).items():
            depth[node] = min(depth.get(node, d), d)

    nodes = []
    for idx, it in enumerate(ordered):
        lag = (it["published_at"] - t0).total_seconds() / 3600
        nodes.append({**it, "published_at": it["published_at"].isoformat(), "order": idx + 1,
                      "hours_since_first": round(lag, 2), "depth": depth.get(it["id"], 0),
                      "is_first_observed": it["id"] == first["id"],
                      "is_transmission_root": trans.in_degree(it["id"]) == 0 and trans.out_degree(it["id"]) > 0})

    status_counts: dict[str, int] = defaultdict(int)
    for _, _, d in g.edges(data=True):
        status_counts[d.get("evidence_status", "kemiripan")] += 1
    platforms_seq: list[str] = []
    for it in ordered:
        if it.get("platform") and it["platform"] not in platforms_seq:
            platforms_seq.append(it["platform"])

    uncertainties: list[dict[str, str]] = [{
        "level": "info",
        "message": "Konten pertama yang teramati belum tentu pencipta asli: konten lebih awal mungkin ada di luar "
                   "cakupan pengumpulan (akun privat, konten terhapus, platform/periode tidak tercakup).",
    }]
    if status_counts.get("kemiripan"):
        uncertainties.append({"level": "peringatan", "message": f"{status_counts['kemiripan']} relasi hanya berbasis kemiripan dan "
                              "TIDAK diperlakukan sebagai transmisi."})
    if len(platforms_seq) > 1:
        cross_confirmed = sum(1 for u, v, d in g.edges(data=True)
                              if by_id[u].get("platform") != by_id[v].get("platform") and d.get("evidence_status") == "atribusi_terkonfirmasi")
        if cross_confirmed == 0:
            uncertainties.append({"level": "peringatan", "message": "Tidak ada atribusi lintas platform yang terkonfirmasi; perpindahan antar-platform masih dugaan."})
    isolated = [n for n in g if g.degree(n) == 0]
    if isolated:
        uncertainties.append({"level": "info", "message": f"{len(isolated)} konten dalam kasus tidak memiliki relasi terdokumentasi."})
    contra_edges = [d for _, _, d in g.edges(data=True) if d.get("contradicting", 0) > 0]
    if contra_edges:
        uncertainties.append({"level": "peringatan", "message": f"{len(contra_edges)} relasi memiliki bukti yang bertentangan dengan dugaan peniruan."})

    span_h = (ordered[-1]["published_at"] - t0).total_seconds() / 3600
    edges = []
    for u, v, d in g.edges(data=True):
        e = {k: val for k, val in d.items()}
        e.setdefault("source", u)
        e.setdefault("target", v)
        edges.append(e)
    return {
        "nodes": nodes,
        "edges": edges,
        "summary": {
            "first_observed_id": first["id"],
            "first_observed_at": t0.isoformat(),
            "originator_known": any(d.get("evidence_status") == "atribusi_terkonfirmasi" and d.get("relation_type") == "atribusi_asal"
                                    for _, _, d in g.edges(data=True)),
            "originator_note": "Pencipta asli tidak dapat dipastikan dari data yang terkumpul. 'Pertama teramati' hanya "
                               "berarti paling awal di dalam dataset.",
            "items": len(items),
            "relations": g.number_of_edges(),
            "transmission_relations": trans.number_of_edges(),
            "max_depth": max(depth.values(), default=0),
            "platforms_sequence": platforms_seq,
            "span_hours": round(span_h, 1),
            "status_counts": dict(status_counts),
        },
        "uncertainties": uncertainties,
    }


def cascade_components(relations: list[tuple[int, int]], min_size: int = 3) -> list[set[int]]:
    g = nx.Graph()
    g.add_edges_from(relations)
    comps = [c for c in nx.connected_components(g) if len(c) >= min_size]
    return sorted(comps, key=lambda c: -len(c))
