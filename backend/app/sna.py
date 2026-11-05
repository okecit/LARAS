"""Fungsi inti Social Network Analysis (NetworkX).

Sentralitas mengukur POSISI dalam jaringan, bukan pengaruh psikologis atau tanggung jawab pidana.
"""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable

import networkx as nx

METRIC_EXPLANATIONS: dict[str, dict[str, str]] = {
    "in_degree": {
        "label": "Sentralitas In-degree",
        "explanation": "Proporsi node lain yang mengarahkan interaksi ke node ini (dibalas, disebut, dibagikan). "
                       "Menunjukkan seberapa sering node menjadi tujuan perhatian dalam data yang terkumpul.",
    },
    "out_degree": {
        "label": "Sentralitas Out-degree",
        "explanation": "Proporsi node lain yang menjadi tujuan interaksi dari node ini. Menunjukkan keaktifan "
                       "memulai interaksi, bukan niat atau pengaruh.",
    },
    "betweenness": {
        "label": "Sentralitas Betweenness",
        "explanation": "Seberapa sering node berada di jalur terpendek antara pasangan node lain. Node dengan nilai "
                       "tinggi dapat menjadi penghubung (jembatan) antar-kelompok dalam struktur jaringan.",
    },
    "closeness": {
        "label": "Sentralitas Closeness",
        "explanation": "Kedekatan rata-rata node ke node lain yang dapat dijangkau (rumus Wasserman–Faust untuk "
                       "graf terputus). Hanya bermakna di dalam komponen yang terhubung; nilai pada graf sangat "
                       "terfragmentasi perlu ditafsirkan hati-hati.",
    },
    "pagerank": {
        "label": "PageRank",
        "explanation": "Skor perhatian rekursif: node bernilai tinggi bila menerima interaksi dari node yang juga "
                       "banyak menerima interaksi. Mengukur posisi struktural, bukan pengaruh nyata.",
    },
    "degree": {
        "label": "Derajat berbobot",
        "explanation": "Jumlah bobot semua edge masuk dan keluar (frekuensi interaksi terdokumentasi).",
    },
}

DISCLAIMER = ("Sentralitas mengukur posisi dalam jaringan data yang terkumpul, bukan pengaruh psikologis, "
              "niat, atau tanggung jawab pidana. Data yang tidak terkumpul dapat mengubah hasil.")


def build_digraph(nodes: Iterable[tuple[str, dict]], edges: Iterable[tuple[str, str, dict]]) -> nx.DiGraph:
    """Bangun DiGraph berbobot. Edge ganda (u,v) digabung: bobot dijumlahkan, tipe dikumpulkan."""
    g = nx.DiGraph()
    for n, attrs in nodes:
        g.add_node(n, **attrs)
    for u, v, attrs in edges:
        if u == v:
            continue
        w = float(attrs.get("weight", 1.0))
        if g.has_edge(u, v):
            d = g[u][v]
            d["weight"] += w
            d["types"] = sorted(set(d.get("types", [])) | set(attrs.get("types", [])))
            d["count"] = d.get("count", 1) + 1
        else:
            data = dict(attrs)
            data["weight"] = w
            data.setdefault("types", [])
            data["count"] = 1
            g.add_edge(u, v, **data)
    return g


def filter_by_weight(g: nx.DiGraph, min_weight: float) -> nx.DiGraph:
    if min_weight <= 1:
        return g
    h = nx.DiGraph()
    h.add_nodes_from(g.nodes(data=True))
    h.add_edges_from((u, v, d) for u, v, d in g.edges(data=True) if d.get("weight", 1) >= min_weight)
    h.remove_nodes_from([n for n in list(h.nodes) if h.degree(n) == 0])
    return h


def compute_centralities(g: nx.DiGraph) -> dict[str, dict[str, float]]:
    """Hitung metrik per node. Jarak untuk betweenness/closeness = 1/bobot (interaksi sering = dekat)."""
    if g.number_of_nodes() == 0:
        return {}
    for _, _, d in g.edges(data=True):
        d["distance"] = 1.0 / max(d.get("weight", 1.0), 1e-9)
    n = g.number_of_nodes()
    in_deg = nx.in_degree_centrality(g) if n > 1 else {x: 0.0 for x in g}
    out_deg = nx.out_degree_centrality(g) if n > 1 else {x: 0.0 for x in g}
    betw = nx.betweenness_centrality(g, weight="distance", normalized=True)
    # closeness pada graf terarah memakai jarak masuk; wf_improved menangani graf terputus
    close = nx.closeness_centrality(g, distance="distance", wf_improved=True)
    try:
        pr = nx.pagerank(g, weight="weight", alpha=0.85, max_iter=200)
    except nx.PowerIterationFailedConvergence:  # pragma: no cover
        pr = {x: 1.0 / n for x in g}
    wdeg = dict(g.degree(weight="weight"))
    return {
        node: {
            "in_degree": round(in_deg[node], 5),
            "out_degree": round(out_deg[node], 5),
            "betweenness": round(betw[node], 5),
            "closeness": round(close[node], 5),
            "pagerank": round(pr[node], 5),
            "degree": float(wdeg[node]),
        }
        for node in g.nodes
    }


def detect_communities(g: nx.DiGraph, seed: int = 42, resolution: float = 1.0) -> tuple[dict[str, int], float]:
    """Louvain pada proyeksi tak-berarah berbobot. Komunitas diurutkan dari terbesar (id 0)."""
    if g.number_of_edges() == 0:
        return {n: i for i, n in enumerate(g.nodes)}, 0.0
    ug = to_undirected_weighted(g)
    comms = nx.community.louvain_communities(ug, weight="weight", seed=seed, resolution=resolution)
    comms = sorted(comms, key=lambda c: (-len(c), min(map(str, c))))
    membership = {node: i for i, c in enumerate(comms) for node in c}
    modularity = nx.community.modularity(ug, comms, weight="weight")
    return membership, round(modularity, 4)


def to_undirected_weighted(g: nx.DiGraph) -> nx.Graph:
    ug = nx.Graph()
    ug.add_nodes_from(g.nodes(data=True))
    for u, v, d in g.edges(data=True):
        w = d.get("weight", 1.0)
        if ug.has_edge(u, v):
            ug[u][v]["weight"] += w
        else:
            ug.add_edge(u, v, weight=w)
    return ug


def network_summary(g: nx.DiGraph, modularity: float | None = None, n_communities: int | None = None) -> dict[str, Any]:
    n, m = g.number_of_nodes(), g.number_of_edges()
    weak = list(nx.weakly_connected_components(g)) if n else []
    strong = nx.number_strongly_connected_components(g) if n else 0
    largest = max((len(c) for c in weak), default=0)
    recip = nx.overall_reciprocity(g) if m else 0.0
    return {
        "nodes": n,
        "edges": m,
        "density": round(nx.density(g), 5) if n > 1 else 0.0,
        "weak_components": len(weak),
        "strong_components": strong,
        "largest_component_size": largest,
        "largest_component_share": round(largest / n, 4) if n else 0.0,
        "reciprocity": round(recip, 4),
        "modularity": modularity,
        "communities": n_communities,
        "total_weight": float(sum(d.get("weight", 1) for _, _, d in g.edges(data=True))),
    }


def shortest_path(g: nx.DiGraph, source: str, target: str, directed: bool = True) -> list[str]:
    """Jalur terpendek berbobot (jarak = 1/bobot). Bila tak ada jalur terarah, coba tak-berarah."""
    for _, _, d in g.edges(data=True):
        d.setdefault("distance", 1.0 / max(d.get("weight", 1.0), 1e-9))
    try:
        return nx.shortest_path(g, source, target, weight="distance")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        if directed:
            return []
    try:
        ug = g.to_undirected(as_view=True)
        return nx.shortest_path(ug, source, target, weight="distance")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return []


def temporal_evolution(timed_edges: list[tuple[str, str, datetime, float]], start: datetime, end: datetime,
                       freq_days: int = 7, cumulative: bool = True) -> list[dict[str, Any]]:
    """Snapshot jaringan per jendela waktu: jumlah node, edge, densitas, komponen, interaksi baru."""
    out = []
    t = start
    seen: list[tuple[str, str, float]] = []
    edges_sorted = sorted(timed_edges, key=lambda e: e[2])
    i = 0
    while t < end:
        t_next = min(t + timedelta(days=freq_days), end)
        window = []
        while i < len(edges_sorted) and edges_sorted[i][2] < t_next:
            if edges_sorted[i][2] >= t or cumulative:
                window.append((edges_sorted[i][0], edges_sorted[i][1], edges_sorted[i][3]))
            i += 1
        seen.extend(window)
        current = seen if cumulative else window
        g = build_digraph([], [(u, v, {"weight": w}) for u, v, w in current])
        out.append({
            "start": t.isoformat(), "end": t_next.isoformat(),
            "new_interactions": len(window),
            "nodes": g.number_of_nodes(), "edges": g.number_of_edges(),
            "density": round(nx.density(g), 5) if g.number_of_nodes() > 1 else 0.0,
            "components": nx.number_weakly_connected_components(g) if g.number_of_nodes() else 0,
        })
        t = t_next
    return out


# --------------------------------------------------------------------------- ekspor

_EXPORT_SAFE = (str, int, float, bool)


def _export_copy(g: nx.DiGraph) -> nx.DiGraph:
    """GraphML/GEXF hanya menerima atribut skalar; list digabung dengan ';', None dibuang."""
    h = nx.DiGraph()
    for n, d in g.nodes(data=True):
        h.add_node(n, **{k: (";".join(map(str, v)) if isinstance(v, (list, tuple, set)) else v)
                         for k, v in d.items() if v is not None and (isinstance(v, _EXPORT_SAFE) or isinstance(v, (list, tuple, set)))})
    for u, v, d in g.edges(data=True):
        h.add_edge(u, v, **{k: (";".join(map(str, x)) if isinstance(x, (list, tuple, set)) else x)
                            for k, x in d.items() if x is not None and (isinstance(x, _EXPORT_SAFE) or isinstance(x, (list, tuple, set)))})
    return h


def export_graphml(g: nx.DiGraph) -> str:
    return "\n".join(nx.generate_graphml(_export_copy(g)))


def export_gexf(g: nx.DiGraph) -> str:
    return "\n".join(nx.generate_gexf(_export_copy(g)))


def export_csv(g: nx.DiGraph, what: str = "edges") -> str:
    buf = io.StringIO()
    if what == "nodes":
        keys = sorted({k for _, d in g.nodes(data=True) for k in d})
        w = csv.writer(buf)
        w.writerow(["id", *keys])
        for n, d in g.nodes(data=True):
            w.writerow([n, *[_cell(d.get(k)) for k in keys]])
    else:
        keys = sorted({k for _, _, d in g.edges(data=True) for k in d} - {"distance"})
        w = csv.writer(buf)
        w.writerow(["source", "target", *keys])
        for u, v, d in g.edges(data=True):
            w.writerow([u, v, *[_cell(d.get(k)) for k in keys]])
    return buf.getvalue()


def _cell(v: Any) -> Any:
    if isinstance(v, (list, tuple, set)):
        return ";".join(map(str, v))
    return "" if v is None else v


def community_profiles(g: nx.DiGraph, membership: dict[str, int], category_attr: str = "categories") -> list[dict]:
    """Ringkasan per komunitas: ukuran, densitas internal, kategori dominan, platform."""
    groups: dict[int, list[str]] = defaultdict(list)
    for n, c in membership.items():
        if n in g:
            groups[c].append(n)
    out = []
    for cid, members in sorted(groups.items()):
        sub = g.subgraph(members)
        cats: dict[str, int] = defaultdict(int)
        plats: dict[str, int] = defaultdict(int)
        for n in members:
            for c in g.nodes[n].get(category_attr, []) or []:
                cats[c] += 1
            p = g.nodes[n].get("platform")
            if p:
                plats[p] += 1
        internal = sum(d.get("weight", 1) for _, _, d in sub.edges(data=True))
        external = sum(d.get("weight", 1) for u, v, d in g.edges(data=True) if (u in sub) != (v in sub))
        out.append({
            "id": cid, "size": len(members),
            "internal_density": round(nx.density(sub), 4) if len(members) > 1 else 0.0,
            "internal_weight": internal, "external_weight": external,
            "categories": dict(sorted(cats.items(), key=lambda x: -x[1])),
            "platforms": dict(sorted(plats.items(), key=lambda x: -x[1])),
        })
    return out
