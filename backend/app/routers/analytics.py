"""Overview, Actor Analytics, Community Detection."""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..db import get_db
from ..deps import graph_filters, require
from ..graphs import GraphFilters, content_categories
from ..services import current_project
from ..sna import DISCLAIMER
from .explorer import _analysis

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), _=Depends(require("view"))):
    proj = current_project(db)
    pid = proj.id
    plats = {p.id: p.code for p in db.scalars(select(m.Platform))}
    contents = db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == pid)).all()
    ccats = content_categories(db, pid)
    by_cat = Counter(c for cats in ccats.values() for c in cats)
    by_cat_ctx: dict[str, Counter] = defaultdict(Counter)
    by_plat_cat: dict[str, Counter] = defaultdict(Counter)
    for c in contents:
        for cat in ccats.get(c.id, []):
            by_cat_ctx[cat][c.context_label] += 1
            by_plat_cat[plats[c.platform_id]][cat] += 1
    status_counts = dict(db.execute(select(m.ContentClassification.validation_status, func.count())
                                    .join(m.ContentItem).where(m.ContentItem.project_id == pid)
                                    .group_by(m.ContentClassification.validation_status)).all())
    rel_counts = dict(db.execute(select(m.ContentRelationship.evidence_status, func.count())
                                 .where(m.ContentRelationship.project_id == pid).group_by(m.ContentRelationship.evidence_status)).all())
    weekly: dict[str, Counter] = defaultdict(Counter)
    for c in contents:
        wk = c.published_at.strftime("%G-W%V")
        for cat in ccats.get(c.id, []):
            weekly[wk][cat] += 1
    _, an = _analysis(db, GraphFilters(layer="aktor"))
    return {
        "totals": {
            "contents": len(contents),
            "actors": db.scalar(select(func.count(m.PseudonymousActor.id)).where(m.PseudonymousActor.project_id == pid)),
            "interactions": db.scalar(select(func.count(m.Interaction.id)).where(m.Interaction.project_id == pid)),
            "relations": db.scalar(select(func.count(m.ContentRelationship.id)).where(m.ContentRelationship.project_id == pid)),
            "classified": len(ccats),
            "evidence": db.scalar(select(func.count(m.EvidenceRecord.id)).where(m.EvidenceRecord.project_id == pid)),
        },
        "by_platform": dict(Counter(plats[c.platform_id] for c in contents)),
        "by_context": dict(Counter(c.context_label for c in contents)),
        "by_category": dict(by_cat),
        "by_category_context": {k: dict(v) for k, v in by_cat_ctx.items()},
        "by_platform_category": {k: dict(v) for k, v in by_plat_cat.items()},
        "validation": status_counts,
        "evidence_status": rel_counts,
        "weekly": [{"week": w, **dict(v)} for w, v in sorted(weekly.items())],
        "network": an["summary"],
    }


@router.get("/actors")
def actors(f: GraphFilters = Depends(graph_filters), db: Session = Depends(get_db), _=Depends(require("view"))):
    """Tabel analitik aktor berpseudonim. Bukan papan peringkat: tidak ada label pelaku atau inferensi usia."""
    f.layer = "aktor"
    proj = current_project(db)
    g, an = _analysis(db, f)
    contents = db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id)).all()
    ccats = content_categories(db, proj.id)
    per_actor: dict[int, Counter] = defaultdict(Counter)
    ctx: dict[int, Counter] = defaultdict(Counter)
    for c in contents:
        per_actor[c.actor_id]["konten"] += 1
        ctx[c.actor_id][c.context_label] += 1
    rows = []
    for n, d in g.nodes(data=True):
        aid = int(n[1:])
        rows.append({"id": n, "pseudonym": d["label"], "platform": d["platform"], "account_category": d["account_category"],
                     "community": an["membership"].get(n, -1), "metrics": an["metrics"].get(n, {}), "contents": per_actor[aid]["konten"],
                     "contexts": dict(ctx[aid]), "categories": d.get("categories", [])})
    # distribusi metrik untuk histogram (lebih aman daripada peringkat)
    dist = {}
    for metric in ("pagerank", "betweenness", "in_degree", "out_degree"):
        vals = sorted(r["metrics"].get(metric, 0) for r in rows)
        dist[metric] = {"min": vals[0] if vals else 0, "median": vals[len(vals) // 2] if vals else 0, "max": vals[-1] if vals else 0}
    return {"actors": rows, "distribution": dist,
            "account_categories": dict(Counter(r["account_category"] for r in rows)), "disclaimer": DISCLAIMER}


@router.get("/communities")
def communities(f: GraphFilters = Depends(graph_filters), db: Session = Depends(get_db), _=Depends(require("view"))):
    g, an = _analysis(db, f)
    profiles = an["communities"]
    # edge antar-komunitas untuk peta meta
    inter: Counter = Counter()
    for u, v, d in g.edges(data=True):
        cu, cv = an["membership"].get(u), an["membership"].get(v)
        if cu is not None and cv is not None and cu != cv:
            inter[(cu, cv)] += d.get("weight", 1)
    bridges = []
    for p in profiles:
        members = [n for n, c in an["membership"].items() if c == p["id"]]
        top = sorted(members, key=lambda n: -an["metrics"].get(n, {}).get("betweenness", 0))[:3]
        p["bridge_nodes"] = [{"id": n, "label": g.nodes[n].get("label"), "betweenness": an["metrics"][n]["betweenness"]} for n in top]
        p["account_categories"] = dict(Counter(g.nodes[n].get("account_category") for n in members if g.nodes[n].get("account_category")))
        p["contexts"] = dict(Counter(g.nodes[n].get("context_label") for n in members if g.nodes[n].get("context_label")))
        bridges.append(p)
    return {"layer": f.layer, "modularity": an["modularity"], "summary": an["summary"], "communities": bridges,
            "inter_community": [{"source": a, "target": b, "weight": w} for (a, b), w in inter.most_common(60)],
            "method": "Louvain (NetworkX, seed=42, resolusi=1.0) pada proyeksi tak-berarah berbobot.",
            "note": "Komunitas adalah pola kepadatan interaksi dalam data, bukan kelompok terorganisasi atau afiliasi."}
