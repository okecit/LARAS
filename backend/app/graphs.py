"""Bangun tiga lapisan jaringan dari basis data dengan filter.

1. aktor     — jaringan interaksi aktor→aktor (berarah, berbobot)
2. konten    — jaringan difusi konten→konten (relasi terdokumentasi + kemiripan, ditandai terpisah)
3. bipartit  — partisipasi aktor→konten (membuat / berinteraksi)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from . import models as m
from .sna import build_digraph, community_profiles, compute_centralities, detect_communities, filter_by_weight, network_summary

LAYERS = {"aktor": "Interaksi aktor–aktor", "konten": "Difusi konten–konten", "bipartit": "Partisipasi aktor–konten"}


@dataclass
class GraphFilters:
    layer: str = "aktor"
    platforms: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    interaction_types: list[str] = field(default_factory=list)
    evidence_statuses: list[str] = field(default_factory=list)
    start: datetime | None = None
    end: datetime | None = None
    min_weight: float = 1.0
    include_similarity: bool = True

    def key(self) -> tuple:
        return (self.layer, tuple(sorted(self.platforms)), tuple(sorted(self.categories)), tuple(sorted(self.interaction_types)),
                tuple(sorted(self.evidence_statuses)), self.start, self.end, self.min_weight, self.include_similarity)


def content_categories(db: Session, project_id: int) -> dict[int, list[str]]:
    """Kategori per konten (label ditolak peninjau dikecualikan)."""
    rows = db.execute(
        select(m.ContentClassification.content_id, m.ContentCategory.code)
        .join(m.ContentCategory, m.ContentCategory.id == m.ContentClassification.category_id)
        .join(m.ContentItem, m.ContentItem.id == m.ContentClassification.content_id)
        .where(m.ContentItem.project_id == project_id, m.ContentClassification.validation_status != "ditolak")
    ).all()
    out: dict[int, list[str]] = defaultdict(list)
    for cid, code in rows:
        if code not in out[cid]:
            out[cid].append(code)
    return out


def _in_window(t: datetime, f: GraphFilters) -> bool:
    return (f.start is None or t >= f.start) and (f.end is None or t <= f.end)


def _cat_ok(cats: list[str], f: GraphFilters) -> bool:
    return not f.categories or bool(set(cats) & set(f.categories))


def _platforms(db: Session) -> dict[int, str]:
    return {p.id: p.code for p in db.scalars(select(m.Platform))}


def _actors(db: Session, project_id: int) -> dict[int, m.PseudonymousActor]:
    return {a.id: a for a in db.scalars(select(m.PseudonymousActor).where(m.PseudonymousActor.project_id == project_id))}


def _contents(db: Session, project_id: int) -> dict[int, m.ContentItem]:
    return {c.id: c for c in db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == project_id))}


def _actor_attrs(a: m.PseudonymousActor, plat: str, cats: list[str]) -> dict[str, Any]:
    return {"label": a.pseudonym, "kind": "aktor", "platform": plat, "account_category": a.account_category,
            "follower_bucket": a.follower_bucket, "categories": cats, "is_demo": a.is_demo}


def _content_attrs(c: m.ContentItem, plat: str, cats: list[str], actor: m.PseudonymousActor | None) -> dict[str, Any]:
    return {"label": c.code, "kind": "konten", "platform": plat, "categories": cats, "content_type": c.content_type,
            "context_label": c.context_label, "published_at": c.published_at.isoformat(),
            "actor": actor.pseudonym if actor else None, "scenario": (c.provenance or {}).get("scenario"), "is_demo": c.is_demo}


def build_graph(db: Session, project_id: int, f: GraphFilters) -> nx.DiGraph:
    if f.layer == "konten":
        return _content_graph(db, project_id, f)
    if f.layer == "bipartit":
        return _bipartite_graph(db, project_id, f)
    return _actor_graph(db, project_id, f)


def _actor_graph(db: Session, project_id: int, f: GraphFilters) -> nx.DiGraph:
    plats, actors, contents = _platforms(db), _actors(db, project_id), _contents(db, project_id)
    ccats = content_categories(db, project_id)
    actor_cats: dict[int, set[str]] = defaultdict(set)
    for c in contents.values():
        actor_cats[c.actor_id].update(ccats.get(c.id, []))
    edges = []
    for it in db.scalars(select(m.Interaction).where(m.Interaction.project_id == project_id)):
        plat = plats[it.platform_id]
        if f.platforms and plat not in f.platforms:
            continue
        if f.interaction_types and it.interaction_type not in f.interaction_types:
            continue
        if not _in_window(it.occurred_at, f):
            continue
        cats = set(ccats.get(it.content_id, [])) | set(ccats.get(it.response_content_id, []))
        if not _cat_ok(list(cats), f):
            continue
        edges.append((f"a{it.source_actor_id}", f"a{it.target_actor_id}", {"weight": it.weight, "types": [it.interaction_type],
                                                                          "platform": plat}))
    used = {u for u, _, _ in edges} | {v for _, v, _ in edges}
    nodes = [(f"a{a.id}", _actor_attrs(a, plats[a.platform_id], sorted(actor_cats.get(a.id, set()))))
             for a in actors.values() if f"a{a.id}" in used]
    return filter_by_weight(build_digraph(nodes, edges), f.min_weight)


def _content_graph(db: Session, project_id: int, f: GraphFilters) -> nx.DiGraph:
    plats, actors, contents = _platforms(db), _actors(db, project_id), _contents(db, project_id)
    ccats = content_categories(db, project_id)
    edges, used = [], set()
    for r in db.scalars(select(m.ContentRelationship).where(m.ContentRelationship.project_id == project_id)):
        s, t = contents.get(r.source_content_id), contents.get(r.target_content_id)
        if not s or not t:
            continue
        if r.evidence_status == "kemiripan" and not f.include_similarity:
            continue
        if f.evidence_statuses and r.evidence_status not in f.evidence_statuses:
            continue
        if f.platforms and (plats[s.platform_id] not in f.platforms or plats[t.platform_id] not in f.platforms):
            continue
        if not (_in_window(s.published_at, f) and _in_window(t.published_at, f)):
            continue
        if f.categories and not (_cat_ok(ccats.get(s.id, []), f) or _cat_ok(ccats.get(t.id, []), f)):
            continue
        edges.append((f"c{s.id}", f"c{t.id}", {
            "weight": 1.0, "types": [r.relation_type], "relation_type": r.relation_type, "evidence_status": r.evidence_status,
            "documented": r.is_platform_documented, "confidence": r.confidence, "relationship_id": r.id,
            "similarity_only": r.evidence_status == "kemiripan"}))
        used.update({s.id, t.id})
    nodes = [(f"c{cid}", _content_attrs(contents[cid], plats[contents[cid].platform_id], ccats.get(cid, []), actors.get(contents[cid].actor_id)))
             for cid in used]
    return build_digraph(nodes, edges)


def _bipartite_graph(db: Session, project_id: int, f: GraphFilters) -> nx.DiGraph:
    plats, actors, contents = _platforms(db), _actors(db, project_id), _contents(db, project_id)
    ccats = content_categories(db, project_id)
    originals = {cid: c for cid, c in contents.items() if c.content_type in ("video", "posting")}
    edges = []
    for c in originals.values():
        plat = plats[c.platform_id]
        if (f.platforms and plat not in f.platforms) or not _in_window(c.published_at, f) or not _cat_ok(ccats.get(c.id, []), f):
            continue
        if not f.interaction_types or "membuat" in f.interaction_types:
            edges.append((f"a{c.actor_id}", f"c{c.id}", {"weight": 1.0, "types": ["membuat"]}))
    for it in db.scalars(select(m.Interaction).where(m.Interaction.project_id == project_id, m.Interaction.content_id.is_not(None))):
        c = originals.get(it.content_id)
        if not c:
            continue
        plat = plats[c.platform_id]
        if (f.platforms and plat not in f.platforms) or not _in_window(it.occurred_at, f) or not _cat_ok(ccats.get(c.id, []), f):
            continue
        if f.interaction_types and it.interaction_type not in f.interaction_types:
            continue
        edges.append((f"a{it.source_actor_id}", f"c{c.id}", {"weight": it.weight, "types": [it.interaction_type]}))
    used = {u for u, _, _ in edges} | {v for _, v, _ in edges}
    nodes: list[tuple[str, dict]] = []
    actor_cats: dict[int, set[str]] = defaultdict(set)
    for c in contents.values():
        actor_cats[c.actor_id].update(ccats.get(c.id, []))
    for a in actors.values():
        if f"a{a.id}" in used:
            nodes.append((f"a{a.id}", _actor_attrs(a, plats[a.platform_id], sorted(actor_cats[a.id]))))
    for c in originals.values():
        if f"c{c.id}" in used:
            nodes.append((f"c{c.id}", _content_attrs(c, plats[c.platform_id], ccats.get(c.id, []), actors.get(c.actor_id))))
    return filter_by_weight(build_digraph(nodes, edges), f.min_weight)


def analyze(g: nx.DiGraph) -> dict[str, Any]:
    metrics = compute_centralities(g)
    membership, modularity = detect_communities(g)
    n_comm = len(set(membership.values())) if membership else 0
    return {"metrics": metrics, "membership": membership, "modularity": modularity,
            "summary": network_summary(g, modularity, n_comm),
            "communities": community_profiles(g, membership)}


def to_cytoscape(g: nx.DiGraph, analysis: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for n, d in g.nodes(data=True):
        nodes.append({**d, "id": n, "community": analysis["membership"].get(n, -1), "metrics": analysis["metrics"].get(n, {})})
    edges = []
    for i, (u, v, d) in enumerate(g.edges(data=True)):
        e = {k: val for k, val in d.items() if k != "distance"}
        edges.append({**e, "id": f"e{i}", "source": u, "target": v})
    return {"nodes": nodes, "edges": edges}


def graph_with_attrs(g: nx.DiGraph, analysis: dict[str, Any]) -> nx.DiGraph:
    """Salin graf dengan metrik & komunitas sebagai atribut node (untuk ekspor)."""
    h = g.copy()
    for n in h.nodes:
        h.nodes[n]["community"] = analysis["membership"].get(n, -1)
        for k, v in analysis["metrics"].get(n, {}).items():
            h.nodes[n][k] = v
    for _, _, d in h.edges(data=True):
        d.pop("distance", None)
    return h


__all__ = ["GraphFilters", "build_graph", "analyze", "to_cytoscape", "graph_with_attrs", "content_categories", "LAYERS", "aliased"]
