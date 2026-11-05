"""Pipeline klasifikasi multi-label kontekstual (baseline berbasis aturan, modular).

Keluaran mesin selalu berstatus `belum_ditinjau` dan wajib divalidasi manusia.
Label melekat pada KONTEN; sistem tidak menyimpulkan usia, identitas, kondisi psikologis,
atau niat kriminal pemilik akun.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from .taxonomy import CONTEXT_DAMPING, CONTEXT_MARKERS
from .textproc import STOPWORDS, contains_term, normalize, tokens

MODEL_VERSION = "aturan-id-0.1.0"


@dataclass
class CategoryLabel:
    code: str
    confidence: float
    raw_score: float
    matched_terms: list[str]
    context_label: str
    rationale: str


@dataclass
class ClassificationResult:
    normalized_text: str
    context_label: str
    context_markers: list[str]
    labels: list[CategoryLabel] = field(default_factory=list)
    model_version: str = MODEL_VERSION


class Classifier(Protocol):  # antarmuka agar model Transformer dapat dipasang kemudian
    version: str

    def classify(self, text: str) -> ClassificationResult: ...


def detect_context(normalized_text: str) -> tuple[str | None, list[str]]:
    """Temukan konteks non-berbahaya dominan (kontra-narasi, berita, edukasi, satire, pencegahan)."""
    hits: dict[str, list[str]] = {}
    for ctx, markers in CONTEXT_MARKERS.items():
        found = [m for m in markers if contains_term(normalized_text, m)]
        if found:
            hits[ctx] = found
    if not hits:
        return None, []
    # prioritas: jumlah penanda, lalu urutan kehati-hatian (edukasi/pencegahan/berita lebih spesifik)
    priority = ["pencegahan", "edukasi", "berita", "kontra_narasi", "satire"]
    # penanda spesifik (edukasi/berita/pencegahan) diberi bobot lebih dari penanda kritik umum ("jangan", "stop")
    best = max(hits, key=lambda c: (len(hits[c]) + (1.0 if c in ("pencegahan", "edukasi", "berita") else 0.0),
                                    -priority.index(c)))
    return best, hits[best]


class RuleClassifier:
    version = MODEL_VERSION

    def __init__(self, categories: Iterable[dict]):
        # categories: [{code, keywords:[{term, weight}], min_confidence}]
        self.categories = [c for c in categories if c.get("is_active", True)]

    def classify(self, text: str) -> ClassificationResult:
        norm = normalize(text or "")
        context, markers = detect_context(norm)
        result = ClassificationResult(normalized_text=norm, context_label=context or "kandidat_berbahaya",
                                      context_markers=markers)
        for cat in self.categories:
            matched, score = [], 0.0
            for kw in cat.get("keywords", []):
                if contains_term(norm, kw["term"]):
                    matched.append(kw["term"])
                    score += float(kw.get("weight", 1.0))
            if not matched or score < 0.75:  # istilah lemah saja tidak cukup
                continue
            conf = 1 - math.exp(-0.8 * score)
            ctx_label = "kandidat_berbahaya"
            rationale = f"Cocok {len(matched)} istilah ({', '.join(matched[:5])})."
            if context:
                conf *= CONTEXT_DAMPING.get(context, 1.0)
                ctx_label = context
                rationale += f" Konteks '{context}' terdeteksi ({', '.join(markers[:3])}); keyakinan berbahaya diturunkan."
            conf = round(min(conf, 0.97), 3)
            # Label topik tetap dicatat walau konteksnya non-berbahaya, agar kontra-narasi ikut terpetakan.
            if conf >= cat.get("min_confidence", 0.35) or context:
                result.labels.append(CategoryLabel(cat["code"], conf, round(score, 2), matched, ctx_label, rationale))
        result.labels.sort(key=lambda l: -l.confidence)
        if not result.labels:
            result.context_label = context or "netral"
        return result


def discover_keywords(texts_by_category: dict[str, list[str]], all_texts: list[str],
                      existing: dict[str, set[str]], top_n: int = 8) -> dict[str, list[dict]]:
    """Usulan kata kunci baru per kategori (log-odds dengan prior). Usulan berstatus `usulan`
    dan hanya masuk kamus setelah diterima peneliti."""
    total = Counter(t for txt in all_texts for t in set(tokens(txt)))
    n_total = max(1, len(all_texts))
    out: dict[str, list[dict]] = {}
    for code, texts in texts_by_category.items():
        if not texts:
            out[code] = []
            continue
        local = Counter(t for txt in texts for t in set(tokens(txt)))
        n_local = len(texts)
        cand = []
        for term, c in local.items():
            if c < 2 or term in STOPWORDS or term in existing.get(code, set()) or term.isdigit():
                continue
            p_local = (c + 0.5) / (n_local + 1)
            p_all = (total[term] + 0.5) / (n_total + 1)
            score = math.log(p_local / p_all)
            if score > 0.4:
                cand.append({"term": term, "score": round(score, 3), "doc_freq": c, "status": "usulan"})
        out[code] = sorted(cand, key=lambda x: -x["score"])[:top_n]
    return out
