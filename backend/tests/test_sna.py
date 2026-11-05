"""Uji fungsi inti jaringan (app.sna)."""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import pytest

from app.sna import (build_digraph, community_profiles, compute_centralities, detect_communities, export_csv, export_gexf,
                     export_graphml, filter_by_weight, network_summary, shortest_path, temporal_evolution)


def star():
    # b, c, d → a (a menerima perhatian)
    return build_digraph([], [("b", "a", {"types": ["balasan"]}), ("c", "a", {"types": ["komentar"]}), ("d", "a", {"types": ["bagikan"]})])


def two_cliques():
    edges = []
    for grp in (["a1", "a2", "a3", "a4"], ["b1", "b2", "b3", "b4"]):
        for u in grp:
            for v in grp:
                if u != v:
                    edges.append((u, v, {"weight": 3}))
    edges.append(("a1", "b1", {"weight": 1}))
    return build_digraph([], edges)


def test_parallel_edges_are_merged_and_weighted():
    g = build_digraph([], [("x", "y", {"types": ["balasan"]}), ("x", "y", {"types": ["sebutan"], "weight": 2}), ("y", "y", {})])
    assert g.number_of_edges() == 1
    assert g["x"]["y"]["weight"] == 3
    assert g["x"]["y"]["types"] == ["balasan", "sebutan"]
    assert not g.has_edge("y", "y")  # self-loop dibuang


def test_in_out_degree_centrality_star():
    m = compute_centralities(star())
    assert m["a"]["in_degree"] == pytest.approx(1.0)
    assert m["a"]["out_degree"] == 0
    assert m["b"]["out_degree"] == pytest.approx(1 / 3, abs=1e-4)
    assert max(m, key=lambda n: m[n]["pagerank"]) == "a"


def test_betweenness_identifies_bridge():
    g = build_digraph([], [("x", "y", {}), ("y", "z", {})])
    m = compute_centralities(g)
    assert m["y"]["betweenness"] > 0
    assert m["x"]["betweenness"] == 0 and m["z"]["betweenness"] == 0


def test_closeness_defined_on_disconnected_graph():
    g = build_digraph([], [("a", "b", {}), ("c", "d", {})])
    m = compute_centralities(g)
    assert all(0 <= v["closeness"] <= 1 for v in m.values())


def test_louvain_recovers_two_communities():
    g = two_cliques()
    membership, modularity = detect_communities(g)
    assert len(set(membership.values())) == 2
    assert membership["a1"] == membership["a4"] != membership["b2"]
    assert modularity > 0.3


def test_detect_communities_is_deterministic():
    g = two_cliques()
    assert detect_communities(g) == detect_communities(g)


def test_summary_density_components():
    g = build_digraph([], [("a", "b", {}), ("b", "a", {}), ("c", "d", {})])
    s = network_summary(g)
    assert s["nodes"] == 4 and s["edges"] == 3
    assert s["density"] == pytest.approx(3 / 12)
    assert s["weak_components"] == 2
    assert s["strong_components"] == 3
    assert s["reciprocity"] == pytest.approx(2 / 3, abs=1e-3)


def test_filter_by_weight_drops_weak_edges_and_isolates():
    g = two_cliques()
    h = filter_by_weight(g, 2)
    assert not h.has_edge("a1", "b1")
    assert h.number_of_nodes() == 8


def test_shortest_path_prefers_heavy_edges_and_falls_back_to_undirected():
    g = build_digraph([], [("a", "b", {"weight": 1}), ("a", "c", {"weight": 10}), ("c", "b", {"weight": 10})])
    assert shortest_path(g, "a", "b") == ["a", "c", "b"]  # jarak 0.2 < 1.0
    assert shortest_path(g, "b", "a", directed=False)[0] == "b"  # tak ada jalur terarah → tak-berarah
    assert shortest_path(g, "b", "a", directed=True) == []
    assert shortest_path(g, "a", "zzz") == []


def test_temporal_evolution_cumulative_growth():
    t0 = datetime(2026, 7, 1, tzinfo=timezone.utc)
    edges = [("a", "b", t0 + timedelta(days=1), 1), ("b", "c", t0 + timedelta(days=9), 1), ("c", "d", t0 + timedelta(days=16), 1)]
    ev = temporal_evolution(edges, t0, t0 + timedelta(days=21))
    assert [w["nodes"] for w in ev] == [2, 3, 4]
    assert [w["new_interactions"] for w in ev] == [1, 1, 1]


def test_exports_are_parseable():
    g = star()
    g.nodes["a"]["categories"] = ["K01", "K03"]
    g.nodes["a"]["metric"] = 0.5
    ET.fromstring(export_graphml(g))
    ET.fromstring(export_gexf(g))
    nodes_csv = export_csv(g, "nodes").splitlines()
    assert nodes_csv[0].startswith("id,")
    assert any("K01;K03" in line for line in nodes_csv)
    assert len(export_csv(g, "edges").splitlines()) == 4


def test_community_profiles():
    g = two_cliques()
    for n in g:
        g.nodes[n]["categories"] = ["K01"] if n.startswith("a") else ["K06"]
    membership, _ = detect_communities(g)
    prof = community_profiles(g, membership)
    assert sorted(p["size"] for p in prof) == [4, 4]
    assert all(len(p["categories"]) == 1 for p in prof)
    assert all(p["external_weight"] == 1 for p in prof)
