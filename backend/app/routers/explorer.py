"""Network Explorer: graf, jalur terpendek, ekspansi node, detail node, ekspor graf."""
from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .. import models as m
from ..cache import cached
from ..config import settings
from ..db import get_db
from ..deps import client_ip, current_user, graph_filters, require
from ..diffusion import EVIDENCE_DESCRIPTIONS, EVIDENCE_LABELS
from ..graphs import LAYERS, GraphFilters, analyze, build_graph, content_categories, graph_with_attrs, to_cytoscape
from ..security import has_permission
from ..services import audit, current_project, mask_text
from ..sna import DISCLAIMER, METRIC_EXPLANATIONS, export_csv, export_gexf, export_graphml, shortest_path, temporal_evolution
from ..taxonomy import CONTEXT_LABELS

router = APIRouter(prefix="/api", tags=["explorer"])


def _analysis(db: Session, f: GraphFilters):
    proj = current_project(db)

    def compute():
        g = build_graph(db, proj.id, f)
        return g, analyze(g)
    return cached(("graph", proj.id, f.key()), compute)


@router.get("/meta")
def meta(db: Session = Depends(get_db), user=Depends(current_user)):
    proj = current_project(db)
    cats = db.scalars(select(m.ContentCategory).order_by(m.ContentCategory.code)).all()
    return {
        "project": {"id": proj.id, "code": proj.code, "name": proj.name, "period_start": proj.period_start.isoformat(),
                    "period_end": proj.period_end.isoformat(), "is_demo": proj.is_demo},
        "data_mode": "DEMO" if proj.is_demo or settings.data_mode == "DEMO" else "LIVE",
        "platforms": [{"code": p.code, "name": p.name, "color": p.color} for p in db.scalars(select(m.Platform).order_by(m.Platform.id))],
        "categories": [{"code": c.code, "name": c.name_id, "color": c.color} for c in cats],
        "layers": LAYERS,
        "interaction_types": ["komentar", "balasan", "bagikan", "kutipan", "remix", "sebutan", "membuat"],
        "evidence_statuses": [{"code": k, "label": v, "description": EVIDENCE_DESCRIPTIONS[k]} for k, v in EVIDENCE_LABELS.items()],
        "context_labels": CONTEXT_LABELS,
        "metrics": METRIC_EXPLANATIONS,
        "disclaimer": DISCLAIMER,
    }


@router.get("/graph")
def graph(f: GraphFilters = Depends(graph_filters), db: Session = Depends(get_db), _=Depends(require("view"))):
    g, an = _analysis(db, f)
    return {"layer": f.layer, **to_cytoscape(g, an), "summary": an["summary"], "communities": an["communities"],
            "disclaimer": DISCLAIMER}


@router.get("/graph/path")
def graph_path(source: str, target: str, f: GraphFilters = Depends(graph_filters), db: Session = Depends(get_db),
               _=Depends(require("view"))):
    g, _an = _analysis(db, f)
    path = shortest_path(g.copy(), source, target, directed=False)  # coba terarah dulu, lalu tak-berarah
    directed = bool(path) and all(g.has_edge(path[i], path[i + 1]) for i in range(len(path) - 1))
    return {"path": path, "length": max(0, len(path) - 1), "directed": directed,
            "note": None if path else "Tidak ada jalur di antara kedua node pada filter saat ini."}


@router.get("/graph/expand")
def graph_expand(node_id: str, layer: str = "aktor", db: Session = Depends(get_db), _=Depends(require("view"))):
    """Tetangga langsung sebuah node pada graf lapisan yang sama TANPA filter kategori/waktu."""
    proj = current_project(db)
    full = cached(("expand_base", proj.id, layer), lambda: build_graph(db, proj.id, GraphFilters(layer=layer)))
    if node_id not in full:
        raise HTTPException(404, "Node tidak ada pada lapisan ini.")
    neigh = set(full.predecessors(node_id)) | set(full.successors(node_id)) | {node_id}
    sub = full.subgraph(neigh)
    nodes = [{**d, "id": n, "community": -1, "metrics": {}} for n, d in sub.nodes(data=True)]
    edges = [{**{k: v for k, v in d.items() if k != "distance"}, "id": f"x_{u}_{v}", "source": u, "target": v}
             for u, v, d in sub.edges(data=True)]
    return {"nodes": nodes, "edges": edges}


@router.get("/graph/export")
def graph_export(request: Request, format: str = "graphml", f: GraphFilters = Depends(graph_filters),
                 db: Session = Depends(get_db), user=Depends(require("export"))):
    g, an = _analysis(db, f)
    h = graph_with_attrs(g, an)
    # Ekspor anonim: hanya pseudonim/kode; tidak ada teks konten atau hash.
    for _, d in h.nodes(data=True):
        d.pop("is_demo", None)
    fname = f"laras_{f.layer}_{'DEMO' if current_project(db).is_demo else 'LIVE'}"
    if format == "graphml":
        body, mt, ext = export_graphml(h), "application/xml", "graphml"
    elif format == "gexf":
        body, mt, ext = export_gexf(h), "application/xml", "gexf"
    elif format in ("csv_nodes", "csv_edges"):
        body, mt, ext = export_csv(h, "nodes" if format == "csv_nodes" else "edges"), "text/csv", f"{format.split('_')[1]}.csv"
    else:
        raise HTTPException(422, "Format: graphml | gexf | csv_nodes | csv_edges")
    audit(db, user, "ekspor_graf", "graf", f.layer, {"format": format, "nodes": h.number_of_nodes()}, client_ip(request))
    db.commit()
    return Response(body, media_type=mt, headers={"Content-Disposition": f'attachment; filename="{fname}.{ext}"'})


@router.get("/sna/temporal")
def sna_temporal(f: GraphFilters = Depends(graph_filters), freq_days: int = 7, db: Session = Depends(get_db),
                 _=Depends(require("view"))):
    proj = current_project(db)
    from datetime import datetime, time, timezone
    start = f.start or datetime.combine(proj.period_start, time.min, tzinfo=timezone.utc)
    end = f.end or datetime.combine(proj.period_end, time.max, tzinfo=timezone.utc)
    plats = {p.id: p.code for p in db.scalars(select(m.Platform))}
    ccats = content_categories(db, proj.id)
    timed = []
    daily: Counter = Counter()
    for it in db.scalars(select(m.Interaction).where(m.Interaction.project_id == proj.id)):
        if f.platforms and plats[it.platform_id] not in f.platforms:
            continue
        if f.interaction_types and it.interaction_type not in f.interaction_types:
            continue
        cats = set(ccats.get(it.content_id, [])) | set(ccats.get(it.response_content_id, []))
        if f.categories and not cats & set(f.categories):
            continue
        timed.append((f"a{it.source_actor_id}", f"a{it.target_actor_id}", it.occurred_at, it.weight))
    content_daily: dict[str, Counter] = defaultdict(Counter)
    for c in db.scalars(select(m.ContentItem).where(m.ContentItem.project_id == proj.id)):
        if not (start <= c.published_at <= end):
            continue
        if f.platforms and plats[c.platform_id] not in f.platforms:
            continue
        cats = ccats.get(c.id, [])
        if f.categories and not set(cats) & set(f.categories):
            continue
        day = c.published_at.date().isoformat()
        daily[day] += 1
        content_daily[day][c.context_label] += 1
    inter_daily = Counter(t.date().isoformat() for _, _, t, _ in timed if start <= t <= end)
    days = sorted(set(daily) | set(inter_daily))
    return {
        "evolution": temporal_evolution([e for e in timed if e[2] <= end], start, end, freq_days),
        "daily": [{"date": d, "content": daily.get(d, 0), "interactions": inter_daily.get(d, 0),
                   "harmful": content_daily[d].get("kandidat_berbahaya", 0),
                   "counter": sum(content_daily[d].get(k, 0) for k in ("kontra_narasi", "edukasi", "pencegahan", "berita"))}
                  for d in days],
    }


# ------------------------------------------------------------------ detail node

def _content_brief(c: m.ContentItem, ccats: dict[int, list[str]], can_raw: bool, plats: dict[int, str]) -> dict:
    return {"id": f"c{c.id}", "db_id": c.id, "code": c.code, "platform": plats[c.platform_id], "content_type": c.content_type,
            "published_at": c.published_at.isoformat(), "context_label": c.context_label, "categories": ccats.get(c.id, []),
            "text": mask_text(c.text_excerpt, can_raw and not c.is_sensitive) if c.text_excerpt else "[teks mentah dihapus — retensi]",
            "metrics": c.metrics, "scenario": (c.provenance or {}).get("scenario"), "is_demo": c.is_demo}


def _evidence_out(e: m.EvidenceRecord) -> dict:
    return {"id": e.id, "relationship_id": e.relationship_id, "content_id": e.content_id, "evidence_type": e.evidence_type,
            "direction": e.direction, "strength": e.strength, "description": e.description, "created_at": e.created_at.isoformat()}


@router.get("/nodes/{node_id}")
def node_detail(node_id: str, db: Session = Depends(get_db), user=Depends(require("view"))):
    proj = current_project(db)
    can_raw = has_permission(user.role, "view_raw")
    plats = {p.id: p.code for p in db.scalars(select(m.Platform))}
    ccats = content_categories(db, proj.id)
    kind, raw_id = node_id[0], node_id[1:]
    if not raw_id.isdigit():
        raise HTTPException(404, "ID node tidak valid.")
    rid = int(raw_id)
    if kind == "a":
        a = db.get(m.PseudonymousActor, rid)
        if not a or a.project_id != proj.id:
            raise HTTPException(404, "Aktor tidak ditemukan.")
        contents = db.scalars(select(m.ContentItem).where(m.ContentItem.actor_id == a.id).order_by(m.ContentItem.published_at)).all()
        inter = db.scalars(select(m.Interaction).where(or_(m.Interaction.source_actor_id == a.id, m.Interaction.target_actor_id == a.id))).all()
        conn: dict[int, dict] = {}
        for it in inter:
            other = it.target_actor_id if it.source_actor_id == a.id else it.source_actor_id
            d = conn.setdefault(other, {"out": 0, "in": 0, "types": Counter()})
            d["out" if it.source_actor_id == a.id else "in"] += 1
            d["types"][it.interaction_type] += 1
        others = {x.id: x for x in db.scalars(select(m.PseudonymousActor).where(m.PseudonymousActor.id.in_(list(conn) or [0])))}
        connected = sorted([{"id": f"a{k}", "label": others[k].pseudonym, "platform": plats[others[k].platform_id],
                             "out": v["out"], "in": v["in"], "types": dict(v["types"])} for k, v in conn.items() if k in others],
                           key=lambda x: -(x["in"] + x["out"]))
        cat_counts = Counter(c for ct in contents for c in ccats.get(ct.id, []))
        ctx_counts = Counter(ct.context_label for ct in contents)
        timeline = Counter(ct.published_at.date().isoformat() for ct in contents)
        inter_tl = Counter(it.occurred_at.date().isoformat() for it in inter)
        ev = db.scalars(select(m.EvidenceRecord).where(m.EvidenceRecord.content_id.in_([c.id for c in contents] or [0]))).all()
        annotations = db.scalars(select(m.Annotation).where(m.Annotation.target_type == "aktor", m.Annotation.target_id == a.id)).all()
        return {
            "kind": "aktor", "id": node_id, "label": a.pseudonym, "platform": plats[a.platform_id],
            "account_category": a.account_category, "follower_bucket": a.follower_bucket,
            "first_seen_at": a.first_seen_at.isoformat() if a.first_seen_at else None,
            "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None, "is_demo": a.is_demo,
            "interaction_totals": {"out": sum(v["out"] for v in conn.values()), "in": sum(v["in"] for v in conn.values()),
                                   "by_type": dict(Counter(it.interaction_type for it in inter))},
            "categories": dict(cat_counts), "contexts": dict(ctx_counts),
            "contents": [_content_brief(c, ccats, can_raw, plats) for c in contents][-30:],
            "connected": connected[:40],
            "timeline": [{"date": d, "content": timeline[d], "interactions": inter_tl.get(d, 0)} for d in sorted(set(timeline) | set(inter_tl))],
            "evidence": [_evidence_out(e) for e in ev],
            "annotations": [_annotation_out(x) for x in annotations],
            "note": "Label kategori melekat pada KONTEN, bukan pada aktor. Sistem tidak menyimpulkan usia, identitas, kondisi "
                    "psikologis, atau niat. Posisi jaringan ≠ tanggung jawab.",
        }
    if kind == "c":
        c = db.get(m.ContentItem, rid)
        if not c or c.project_id != proj.id:
            raise HTTPException(404, "Konten tidak ditemukan.")
        rels = db.scalars(select(m.ContentRelationship).where(or_(m.ContentRelationship.source_content_id == c.id,
                                                                   m.ContentRelationship.target_content_id == c.id))).all()
        rel_ids = [r.id for r in rels]
        ev = db.scalars(select(m.EvidenceRecord).where(or_(m.EvidenceRecord.content_id == c.id,
                                                           m.EvidenceRecord.relationship_id.in_(rel_ids or [0])))).all()
        other_ids = {r.source_content_id if r.target_content_id == c.id else r.target_content_id for r in rels}
        others = {x.id: x for x in db.scalars(select(m.ContentItem).where(m.ContentItem.id.in_(list(other_ids) or [0])))}
        inter = db.scalars(select(m.Interaction).where(m.Interaction.content_id == c.id)).all()
        annotations = db.scalars(select(m.Annotation).where(m.Annotation.target_type == "konten", m.Annotation.target_id == c.id)).all()
        return {
            "kind": "konten", "id": node_id, "label": c.code, **_content_brief(c, ccats, can_raw, plats),
            "actor": {"id": f"a{c.actor_id}", "label": c.actor.pseudonym},
            "classifications": [{"id": k.id, "code": k.category.code, "name": k.category.name_id, "confidence": k.confidence,
                                 "method": k.method, "model_version": k.model_version, "context_label": k.context_label,
                                 "matched_terms": k.matched_terms, "rationale": k.rationale, "validation_status": k.validation_status,
                                 "reviewer_note": k.reviewer_note} for k in c.classifications],
            "relations": [{"id": r.id, "direction": "keluar" if r.source_content_id == c.id else "masuk",
                           "other": {"id": f"c{o.id}", "code": o.code, "platform": plats[o.platform_id], "published_at": o.published_at.isoformat()},
                           "relation_type": r.relation_type, "evidence_status": r.evidence_status, "documented": r.is_platform_documented,
                           "confidence": r.confidence, "time_lag_hours": r.time_lag_hours}
                          for r in rels if (o := others.get(r.target_content_id if r.source_content_id == c.id else r.source_content_id))],
            "interaction_totals": dict(Counter(it.interaction_type for it in inter)),
            "timeline": [{"date": d, "interactions": n} for d, n in sorted(Counter(it.occurred_at.date().isoformat() for it in inter).items())],
            "evidence": [_evidence_out(e) for e in ev],
            "annotations": [_annotation_out(x) for x in annotations],
            "provenance": {"source_id": c.source_id, "collected_at": c.collected_at.isoformat(), "access_level": c.access_level,
                           "tz_original": c.published_tz_original, **{k: v for k, v in (c.provenance or {}).items() if k != "key"}},
        }
    raise HTTPException(404, "Jenis node tidak dikenal.")


def _annotation_out(a: m.Annotation) -> dict:
    return {"id": a.id, "target_type": a.target_type, "target_id": a.target_id, "kind": a.kind, "body": a.body, "tags": a.tags,
            "review_status": a.review_status, "author_id": a.author_id, "reviewed_by": a.reviewed_by,
            "created_at": a.created_at.isoformat()}
