"""Konektor per platform. Struktur respons mengikuti dokumentasi resmi masing-masing API."""
from __future__ import annotations

from typing import Any, Iterator

from .base import AuthStatus, BaseConnector, NormalizedItem, NotAuthorized, NotAvailable, parse_timestamp


class YouTubeConnector(BaseConnector):
    """YouTube Data API v3 — search.list (100 unit), videos.list (1 unit), commentThreads.list (1 unit)."""

    key, platform, label = "youtube", "youtube", "YouTube Data API v3"
    credential_envs = ["YSNA_YOUTUBE_API_KEY"]
    docs_url = "https://developers.google.com/youtube/v3/docs"
    notes = "Hanya video & komentar publik. Kuota bawaan 10.000 unit/hari."
    BASE = "https://www.googleapis.com/youtube/v3"

    def check_authorization(self) -> AuthStatus:
        base = super().check_authorization()
        if base.status != "terkonfigurasi":
            return base
        try:
            self._request("GET", f"{self.BASE}/i18nLanguages", units=1, params={"part": "snippet", "key": self.credentials()["YSNA_YOUTUBE_API_KEY"]})
            return AuthStatus("terotorisasi", "Kunci API valid.")
        except NotAuthorized as e:
            return AuthStatus("ditolak", str(e))
        except Exception as e:  # noqa: BLE001
            return AuthStatus("terkonfigurasi", f"Tidak dapat memverifikasi: {e}")

    def fetch(self, query: str, params: dict[str, Any]) -> Iterator[NormalizedItem]:
        key = self.credentials()["YSNA_YOUTUBE_API_KEY"]
        if not key:
            raise NotAuthorized("YSNA_YOUTUBE_API_KEY belum disetel.")
        sp = {"part": "snippet", "q": query, "type": "video", "maxResults": min(int(params.get("max_results", 25)), 50),
              "regionCode": params.get("region", "ID"), "relevanceLanguage": "id", "key": key}
        if params.get("published_after"):
            sp["publishedAfter"] = params["published_after"]
        if params.get("published_before"):
            sp["publishedBefore"] = params["published_before"]
        search = self._request("GET", f"{self.BASE}/search", units=100, params=sp).json()
        ids = [it["id"]["videoId"] for it in search.get("items", []) if it.get("id", {}).get("videoId")]
        if not ids:
            return
        videos = self._request("GET", f"{self.BASE}/videos", units=1,
                               params={"part": "snippet,statistics", "id": ",".join(ids), "key": key}).json()
        for v in videos.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            yield NormalizedItem(platform="youtube", external_id=v["id"], author_handle=sn["channelId"],
                                 published_at=parse_timestamp(sn["publishedAt"]), text=f"{sn.get('title', '')}\n{sn.get('description', '')[:500]}",
                                 content_type="video", has_media=True,
                                 metrics={"tayangan": int(st.get("viewCount", 0)), "suka": int(st.get("likeCount", 0)),
                                          "komentar": int(st.get("commentCount", 0))},
                                 provenance={"api": "youtube.videos.list", "query": query})
            if params.get("include_comments", True):
                yield from self._comments(v["id"], sn["channelId"], key, int(params.get("max_comments", 20)))

    def _comments(self, video_id: str, channel_id: str, key: str, limit: int) -> Iterator[NormalizedItem]:
        try:
            data = self._request("GET", f"{self.BASE}/commentThreads", units=1,
                                 params={"part": "snippet,replies", "videoId": video_id, "maxResults": min(limit, 100),
                                         "textFormat": "plainText", "key": key}).json()
        except NotAuthorized as e:  # komentar dinonaktifkan
            self.log_event("info", f"Komentar {video_id} tidak tersedia: {e}")
            return
        for th in data.get("items", []):
            top = th["snippet"]["topLevelComment"]
            s = top["snippet"]
            author = s.get("authorChannelId", {}).get("value") or s.get("authorDisplayName", "anon")
            yield NormalizedItem(platform="youtube", external_id=top["id"], author_handle=author,
                                 published_at=parse_timestamp(s["publishedAt"]), text=s.get("textOriginal", ""),
                                 content_type="komentar", parent_external_id=video_id, parent_author_handle=channel_id,
                                 relation_type="balasan_dari", interaction_type="komentar",
                                 metrics={"suka": int(s.get("likeCount", 0))}, provenance={"api": "youtube.commentThreads.list"})
            for rep in th.get("replies", {}).get("comments", []):
                rs = rep["snippet"]
                yield NormalizedItem(platform="youtube", external_id=rep["id"],
                                     author_handle=rs.get("authorChannelId", {}).get("value") or "anon",
                                     published_at=parse_timestamp(rs["publishedAt"]), text=rs.get("textOriginal", ""),
                                     content_type="balasan", parent_external_id=top["id"], parent_author_handle=author,
                                     relation_type="balasan_dari", interaction_type="balasan",
                                     provenance={"api": "youtube.commentThreads.list"})


class XConnector(BaseConnector):
    """X API v2 — GET /2/tweets/search/recent (bergantung tingkat akses & ketentuan)."""

    key, platform, label = "x_api", "x", "X API v2 — Recent Search"
    credential_envs = ["YSNA_X_BEARER_TOKEN"]
    docs_url = "https://docs.x.com/x-api/posts/search-recent-posts"
    notes = "Pencarian 7 hari terakhir pada tingkat akses umum; kuota & cakupan tergantung paket akses Anda."
    BASE = "https://api.x.com/2"
    requests_per_sec = 0.2

    def fetch(self, query: str, params: dict[str, Any]) -> Iterator[NormalizedItem]:
        token = self.credentials()["YSNA_X_BEARER_TOKEN"]
        if not token:
            raise NotAuthorized("YSNA_X_BEARER_TOKEN belum disetel.")
        p = {"query": f"({query}) lang:id", "max_results": min(int(params.get("max_results", 50)), 100),
             "tweet.fields": "created_at,public_metrics,referenced_tweets,in_reply_to_user_id,conversation_id,entities,author_id",
             "expansions": "author_id,referenced_tweets.id,referenced_tweets.id.author_id", "user.fields": "username"}
        if params.get("start_time"):
            p["start_time"] = params["start_time"]
        data = self._request("GET", f"{self.BASE}/tweets/search/recent", units=1, params=p,
                             headers={"Authorization": f"Bearer {token}"}).json()
        yield from self.normalize_response(data)

    @staticmethod
    def normalize_response(data: dict[str, Any]) -> Iterator[NormalizedItem]:
        includes = data.get("includes", {})
        ref_authors = {t["id"]: t.get("author_id") for t in includes.get("tweets", [])}
        rel_map = {"replied_to": ("balasan_dari", "balasan", "balasan"), "quoted": ("kutipan_dari", "kutipan", "kutipan"),
                   "retweeted": ("repost_dari", "bagikan", "repost")}
        for t in data.get("data", []):
            refs = t.get("referenced_tweets") or []
            rel = refs[0] if refs else None
            relation, itype, ctype = rel_map.get(rel["type"], (None, None, "posting")) if rel else (None, None, "posting")
            pm = t.get("public_metrics", {})
            yield NormalizedItem(
                platform="x", external_id=t["id"], author_handle=t["author_id"], published_at=parse_timestamp(t["created_at"]),
                text=t.get("text", ""), content_type=ctype,
                metrics={"suka": pm.get("like_count", 0), "komentar": pm.get("reply_count", 0),
                         "bagikan": pm.get("retweet_count", 0) + pm.get("quote_count", 0)},
                parent_external_id=rel["id"] if rel else None,
                parent_author_handle=ref_authors.get(rel["id"]) if rel else None,
                relation_type=relation, interaction_type=itype,
                mentions=[m_["id"] for m_ in (t.get("entities", {}) or {}).get("mentions", []) if m_.get("id")],
                provenance={"api": "x.tweets.search.recent"})


class TikTokResearchConnector(BaseConnector):
    """TikTok Research API — hanya untuk peneliti yang disetujui TikTok (kelayakan & persetujuan wajib)."""

    key, platform, label = "tiktok_research", "tiktok", "TikTok Research API"
    credential_envs = ["YSNA_TIKTOK_CLIENT_KEY", "YSNA_TIKTOK_CLIENT_SECRET"]
    docs_url = "https://developers.tiktok.com/doc/research-api-get-started"
    availability = "memerlukan_persetujuan"
    notes = ("Memerlukan persetujuan program TikTok Research API untuk institusi Anda. Tanpa persetujuan, gunakan impor "
             "CSV/JSON dari data yang diperoleh secara sah.")
    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    QUERY_URL = "https://open.tiktokapis.com/v2/research/video/query/"
    FIELDS = "id,video_description,create_time,username,like_count,comment_count,share_count,view_count,region_code,hashtag_names"

    def _token(self) -> str:
        c = self.credentials()
        resp = self._request("POST", self.TOKEN_URL, units=0, data={
            "client_key": c["YSNA_TIKTOK_CLIENT_KEY"], "client_secret": c["YSNA_TIKTOK_CLIENT_SECRET"],
            "grant_type": "client_credentials"}, headers={"Content-Type": "application/x-www-form-urlencoded"})
        tok = resp.json().get("access_token")
        if not tok:
            raise NotAuthorized(f"Token tidak diberikan: {resp.text[:200]}")
        return tok

    def check_authorization(self) -> AuthStatus:
        base = super().check_authorization()
        if base.status != "terkonfigurasi":
            return AuthStatus("memerlukan_persetujuan", base.message + ". " + self.notes)
        try:
            self._token()
            return AuthStatus("terotorisasi", "Token klien diterbitkan oleh TikTok.")
        except NotAuthorized as e:
            return AuthStatus("ditolak", str(e))
        except Exception as e:  # noqa: BLE001
            return AuthStatus("terkonfigurasi", f"Tidak dapat memverifikasi: {e}")

    def fetch(self, query: str, params: dict[str, Any]) -> Iterator[NormalizedItem]:
        if not self.is_configured():
            raise NotAuthorized("Kredensial TikTok Research API belum disetel / belum disetujui.")
        tok = self._token()
        body = {"query": {"and": [{"operation": "IN", "field_name": "region_code", "field_values": ["ID"]},
                                  {"operation": "IN", "field_name": "keyword", "field_values": [q.strip() for q in query.split(",")]}]},
                "start_date": params.get("start_date", "20260701"), "end_date": params.get("end_date", "20260730"),
                "max_count": min(int(params.get("max_results", 100)), 100)}
        data = self._request("POST", f"{self.QUERY_URL}?fields={self.FIELDS}", units=1, json=body,
                             headers={"Authorization": f"Bearer {tok}"}).json()
        for v in data.get("data", {}).get("videos", []):
            yield NormalizedItem(platform="tiktok", external_id=str(v["id"]), author_handle=v.get("username", "anon"),
                                 published_at=parse_timestamp(v["create_time"]), text=v.get("video_description", ""),
                                 content_type="video", has_media=True,
                                 metrics={"tayangan": v.get("view_count", 0), "suka": v.get("like_count", 0),
                                          "komentar": v.get("comment_count", 0), "bagikan": v.get("share_count", 0)},
                                 provenance={"api": "tiktok.research.video.query", "hashtags": v.get("hashtag_names", [])})


class MetaContentLibraryConnector(BaseConnector):
    """Meta Content Library — PLACEHOLDER. Akses MCL melalui lingkungan aman Meta (bukan REST API publik)."""

    key, platform, label = "meta_content_library", "instagram", "Meta Content Library (Instagram/Facebook)"
    docs_url = "https://transparency.meta.com/researchtools/meta-content-library"
    availability = "placeholder"
    notes = ("Integrasi langsung tidak tersedia: MCL diakses melalui lingkungan bersih Meta/mitra (mis. SOMAR/ICPSR). "
             "Alur sah: ekspor data yang diizinkan dari lingkungan tersebut sesuai ketentuan, lalu impor melalui modul "
             "Impor CSV/JSON dengan sumber 'Meta Content Library (ekspor resmi)'.")

    def fetch(self, query: str, params: dict[str, Any]) -> Iterator[NormalizedItem]:
        raise NotAvailable(self.notes)


class FileImportConnector(BaseConnector):
    key, platform, label = "file_import", "lainnya", "Impor CSV/JSON"
    notes = "Unggah berkas CSV/JSON dari sumber yang sah. Validasi skema, normalisasi waktu, dan deduplikasi otomatis."

    def check_authorization(self) -> AuthStatus:
        return AuthStatus("terotorisasi", "Selalu tersedia; dasar hukum dicatat per impor.")

    def fetch(self, query: str, params: dict[str, Any]) -> Iterator[NormalizedItem]:
        raise NotAvailable("Gunakan endpoint /api/import untuk impor berkas.")


REGISTRY: dict[str, type[BaseConnector]] = {c.key: c for c in
                                            [YouTubeConnector, XConnector, TikTokResearchConnector, MetaContentLibraryConnector, FileImportConnector]}


def get_connector(key: str, **kw) -> BaseConnector:
    if key not in REGISTRY:
        raise KeyError(f"Konektor tidak dikenal: {key}")
    return REGISTRY[key](**kw)
