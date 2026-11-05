"""Uji asap API end-to-end di atas dataset DEMO (SQLite sementara)."""
import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.seed import DEMO_PASSWORD, seed_demo_data


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_demo_data(db)
        db.commit()
    return TestClient(app)


def login(client, user):
    r = client.post("/api/auth/login", json={"username": user, "password": DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_requires_auth(client):
    assert client.get("/api/graph").status_code == 401
    assert client.post("/api/auth/login", json={"username": "ketua", "password": "salah"}).status_code == 401


@pytest.mark.parametrize("layer", ["aktor", "konten", "bipartit"])
def test_graph_layers(client, layer):
    h = login(client, "peneliti")
    r = client.get(f"/api/graph?layer={layer}", headers=h)
    assert r.status_code == 200
    g = r.json()
    assert g["nodes"] and g["edges"]
    assert {"pagerank", "betweenness", "in_degree"} <= set(g["nodes"][0]["metrics"])
    assert g["summary"]["modularity"] is not None


def test_graph_filters_reduce(client):
    h = login(client, "peneliti")
    full = client.get("/api/graph?layer=aktor", headers=h).json()["summary"]["edges"]
    k06 = client.get("/api/graph?layer=aktor&categories=K06&platforms=x", headers=h).json()["summary"]["edges"]
    assert 0 < k06 < full


def test_node_detail_and_text_masking(client):
    g = client.get("/api/graph?layer=konten", headers=login(client, "peneliti")).json()
    cid = next(n["id"] for n in g["nodes"] if n["label"] == "ABL-C1")
    d = client.get(f"/api/nodes/{cid}", headers=login(client, "peneliti")).json()
    assert "gaya jalan" in d["text"]
    assert d["classifications"][0]["code"] == "K01"
    masked = client.get(f"/api/nodes/{cid}", headers=login(client, "pengamat")).json()
    assert "dibatasi" in masked["text"]


def test_ableism_cascade(client):
    h = login(client, "peneliti")
    cases = client.get("/api/diffusion/cases", headers=h).json()
    assert cases[0]["id"] == "ABL-01"
    c = client.get("/api/diffusion/cascade/ABL-01", headers=h).json()
    nodes = {n["code"]: n for n in c["nodes"]}
    assert nodes["ABL-C00"]["is_first_observed"]  # pertama teramati ≠ video viral
    assert not nodes["ABL-C1"]["is_first_observed"] and nodes["ABL-C1"]["is_transmission_root"]
    assert set(c["summary"]["status_counts"]) == {"kemiripan", "kemungkinan_replikasi", "replikasi_didukung", "atribusi_terkonfirmasi"}
    assert {"instagram", "tiktok", "x", "youtube"} <= set(c["summary"]["platforms_sequence"])


def test_status_cannot_exceed_evidence(client):
    h = login(client, "peninjau")
    c = client.get("/api/diffusion/cascade/JDL-01", headers=h).json()
    rel = next(e for e in c["edges"] if e["evidence_status"] == "kemiripan")
    r = client.patch(f"/api/diffusion/relations/{rel['id']}/status", json={"evidence_status": "atribusi_terkonfirmasi"}, headers=h)
    assert r.status_code == 422


def test_rbac(client):
    h = login(client, "pengamat")
    assert client.get("/api/graph/export?format=graphml", headers=h).status_code == 403
    assert client.post("/api/classifications/1/review", json={"decision": "valid"}, headers=h).status_code == 403
    assert client.get("/api/users", headers=login(client, "peneliti")).status_code == 403
    assert client.get("/api/users", headers=login(client, "admin")).status_code == 200


def test_exports(client):
    h = login(client, "peneliti")
    for fmt in ("graphml", "gexf", "csv_nodes", "csv_edges"):
        r = client.get(f"/api/graph/export?format={fmt}&layer=aktor", headers=h)
        assert r.status_code == 200 and len(r.content) > 100
    anon = client.get("/api/export/anonymized", headers=h).json()
    assert anon["meta"]["data_mode"] == "DEMO" and not anon["meta"]["text_included"]
    assert all("text" not in c for c in anon["contents"])
    assert client.get("/api/export/anonymized?include_text=true", headers=h).status_code == 403
    assert all(c["body"] for c in anon["approved_conclusions"])


def test_import_dry_run_then_commit(client):
    h = login(client, "ketua")
    sources = client.get("/api/sources", headers=h).json()
    sid = next(s["id"] for s in sources if s["connector_key"] == "file_import")
    csv = (b"platform,external_id,author_handle,published_at,text,content_type,parent_external_id,interaction_type\n"
           b"x,t1,akun_uji,2026-08-01T10:00:00+07:00,slot gacor maxwin link di bio,posting,,\n"
           b"x,t2,akun_uji2,2026-08-01T11:00:00+07:00,hati-hati judol jangan tergiur maxwin,balasan,t1,balasan\n")
    data = {"source_id": str(sid), "legal_basis": "Data uji internal, tanpa data pribadi nyata.", "dry_run": "true"}
    r = client.post("/api/import", files={"file": ("uji.csv", csv, "text/csv")}, data=data, headers=h)
    assert r.status_code == 200 and r.json()["validation"]["valid_rows"] == 2 and "result" not in r.json()
    data["dry_run"] = "false"
    r = client.post("/api/import", files={"file": ("uji.csv", csv, "text/csv")}, data=data, headers=h).json()
    assert r["result"]["new"] == 2 and r["result"]["relations"] == 1
    again = client.post("/api/import", files={"file": ("uji.csv", csv, "text/csv")}, data=data, headers=h).json()
    assert again["result"]["new"] == 0 and again["result"]["duplicate"] == 2


def test_conclusion_needs_second_reviewer(client):
    h = login(client, "ketua")
    a = client.post("/api/annotations", json={"target_type": "proyek", "kind": "kesimpulan", "body": "Kesimpulan uji"}, headers=h).json()
    assert a["review_status"] == "perlu_tinjauan"
    assert client.post(f"/api/annotations/{a['id']}/review", json={"decision": "disetujui"}, headers=h).status_code == 422
    r = client.post(f"/api/annotations/{a['id']}/review", json={"decision": "disetujui"}, headers=login(client, "peninjau"))
    assert r.json()["review_status"] == "disetujui"


def test_overview_actors_communities_temporal(client):
    h = login(client, "peneliti")
    assert client.get("/api/overview", headers=h).json()["totals"]["contents"] > 500
    assert client.get("/api/actors", headers=h).json()["actors"]
    assert len(client.get("/api/communities", headers=h).json()["communities"]) >= 3
    assert client.get("/api/sna/temporal", headers=h).json()["evolution"]
    assert client.get("/api/graph/path?source=a1&target=a2", headers=h).status_code == 200
