"""Normalisasi teks media sosial Indonesia & kemiripan semantik ringan (tanpa dependensi berat)."""
from __future__ import annotations

import math
import re
from collections import Counter

SLANG: dict[str, str] = {
    "gk": "gak", "ga": "gak", "nggak": "gak", "ngga": "gak", "enggak": "gak", "tdk": "tidak", "g": "gak",
    "yg": "yang", "dgn": "dengan", "dg": "dengan", "utk": "untuk", "bgt": "banget", "bngt": "banget",
    "aja": "saja", "aj": "saja", "sm": "sama", "jd": "jadi", "krn": "karena", "karna": "karena",
    "tp": "tapi", "trs": "terus", "udh": "sudah", "udah": "sudah", "blm": "belum", "lg": "lagi",
    "org": "orang", "bkn": "bukan", "klo": "kalau", "kalo": "kalau", "gmn": "gimana", "dr": "dari",
    "sy": "saya", "gw": "gue", "gua": "gue", "lu": "lo", "lo": "lo", "elu": "lo", "km": "kamu",
    "bs": "bisa", "jgn": "jangan", "skrg": "sekarang", "pd": "pada", "sdh": "sudah", "ntar": "nanti",
    "anjir": "anjir", "anjay": "anjir", "wkwkwk": "wkwk", "wkwkwkwk": "wkwk", "awokwok": "wkwk", "xixixi": "wkwk",
    "hp": "hp", "nomer": "nomor", "jdul": "judol", "gcor": "gacor",
}

LEET = str.maketrans({"4": "a", "1": "i", "3": "e", "0": "o", "5": "s", "7": "t", "@": "a", "$": "s"})

STOPWORDS = set("""yang dan di ke dari ini itu dengan untuk pada adalah karena juga ada tidak gak sudah saja
bisa akan jadi lagi kalau tapi atau sama aku kamu dia kita mereka gue lo nya banget deh dong sih kok
yg se para oleh dalam sebagai tersebut seperti lebih harus masih belum pun lah kan ya the a of to in""".split())

_URL = re.compile(r"https?://\S+|www\.\S+")
_MENTION = re.compile(r"@\w+")
_REPEAT = re.compile(r"(\w)\1{2,}")
_NONWORD = re.compile(r"[^\w\s#/-]")
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Huruf kecil, URL/mention disamarkan, huruf berulang dipadatkan, leetspeak & slang dinormalkan."""
    if not text:
        return ""
    t = text.lower()
    t = _URL.sub(" __url__ ", t)
    t = _MENTION.sub(" __user__ ", t)
    t = t.replace("#", " ")
    tokens = []
    for tok in _WS.split(_NONWORD.sub(" ", t)):
        if not tok:
            continue
        if re.search(r"[a-z]", tok) and re.search(r"[0-9@$]", tok) and not tok.startswith("__"):
            tok = tok.translate(LEET)
        tok = _REPEAT.sub(r"\1", tok)
        tok = {"__url__": "<url>", "__user__": "@user"}.get(tok, tok)
        tokens.append(SLANG.get(tok, tok))
    return " ".join(tokens).strip()


def tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t not in STOPWORDS and len(t) > 1 and t not in {"<url>", "@user"}]


def _char_ngrams(text: str, n: int = 3) -> Counter:
    s = f" {normalize(text)} "
    return Counter(s[i:i + n] for i in range(max(0, len(s) - n + 1)))


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def similarity(a: str, b: str) -> float:
    """Kemiripan 0–1: gabungan kosinus n-gram karakter (tahan ejaan) dan Jaccard token.

    Nilai ini HANYA menunjukkan kemiripan permukaan teks, bukan bukti peniruan/transmisi.
    """
    if not a or not b:
        return 0.0
    cos = _cosine(_char_ngrams(a), _char_ngrams(b))
    ta, tb = set(tokens(a)), set(tokens(b))
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return round(0.7 * cos + 0.3 * jac, 4)


def contains_term(normalized_text: str, term: str) -> bool:
    nt = normalize(term)
    if not nt:
        return False
    return re.search(rf"(?<!\w){re.escape(nt)}(?!\w)", normalized_text) is not None
