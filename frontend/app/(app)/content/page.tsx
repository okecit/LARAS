"use client";

import { Check, Plus, RefreshCw, Save, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Page } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import {
  Badge, Card, CardHeader, Dot, Empty, ErrorBox, Input, Notice, PageHeader, Select, Spinner, Tabs, Textarea,
} from "@/components/ui/primitives";
import { api, qs } from "@/lib/api";
import { CONTEXT_COLORS, CONTEXT_LABELS, fmtDateTime, PLATFORM_NAMES, VALIDATION_LABELS } from "@/lib/format";
import { useApi, useApp } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Tab = "taksonomi" | "tinjauan" | "uji" | "kata_kunci" | "kemiripan";

export default function ContentIntelligence() {
  const { can } = useApp();
  const [tab, setTab] = useState<Tab>("taksonomi");
  const [msg, setMsg] = useState<string | null>(null);
  async function reclassify() {
    const r = await api<any>("/api/classify/run", { method: "POST" });
    setMsg(`Klasifikasi ulang selesai: ${r.items} konten, ${r.labels} label (keputusan manusia dipertahankan).`);
  }
  return (
    <Page>
      <PageHeader title="Content Intelligence"
        subtitle="Taksonomi perilaku K01–K08, klasifikasi multi-label kontekstual, dan tinjauan manusia. Label melekat pada konten—bukan pada pemilik akun."
        right={can("edit_taxonomy") && <Button variant="secondary" onClick={reclassify}><RefreshCw />Klasifikasi ulang semua</Button>} />
      {msg && <div className="mb-3"><Notice>{msg}</Notice></div>}
      <Tabs className="mb-4" value={tab} onChange={setTab} items={[
        { value: "taksonomi", label: "Taksonomi" }, { value: "tinjauan", label: "Antrean tinjauan" }, { value: "uji", label: "Uji klasifikasi" },
        { value: "kata_kunci", label: "Penemuan kata kunci" }, { value: "kemiripan", label: "Kemiripan semantik" },
      ]} />
      {tab === "taksonomi" && <Taxonomy />}
      {tab === "tinjauan" && <ReviewQueue />}
      {tab === "uji" && <TestClassifier />}
      {tab === "kata_kunci" && <KeywordDiscovery />}
      {tab === "kemiripan" && <Similarity />}
    </Page>
  );
}

function Taxonomy() {
  const { data, error, reload } = useApi<any[]>("/api/categories");
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return <Spinner />;
  return <div className="grid gap-4 xl:grid-cols-2">{data.map((c) => <CategoryCard key={c.code} c={c} onSaved={reload} />)}</div>;
}

function CategoryCard({ c, onSaved }: { c: any; onSaved: () => void }) {
  const { can } = useApp();
  const [kw, setKw] = useState<{ term: string; weight: number }[]>(c.keywords);
  const [term, setTerm] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const dirty = JSON.stringify(kw) !== JSON.stringify(c.keywords);
  const editable = can("edit_taxonomy");
  async function save() {
    setBusy(true);
    setErr(null);
    try {
      await api(`/api/categories/${c.code}`, { method: "PATCH", body: JSON.stringify({ keywords: kw }) });
      onSaved();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2"><Dot color={c.color} size={10} /><span className="font-mono text-dim">{c.code}</span>{c.name}</span>}
        subtitle={`${c.name_en} · versi ${c.version} · ambang keyakinan ${c.min_confidence}`} />
      <div className="space-y-3 p-4 text-xs">
        <p className="leading-relaxed text-mute">{c.definition}</p>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <div className="label-xs mb-1 text-teal/80">Kriteria inklusi</div>
            <ul className="list-disc space-y-0.5 pl-4 text-2xs text-mute">{c.inclusion_criteria.map((x: string) => <li key={x}>{x}</li>)}</ul>
          </div>
          <div>
            <div className="label-xs mb-1 text-danger/80">Kriteria eksklusi</div>
            <ul className="list-disc space-y-0.5 pl-4 text-2xs text-mute">{c.exclusion_criteria.map((x: string) => <li key={x}>{x}</li>)}</ul>
          </div>
        </div>
        <div>
          <div className="label-xs mb-1">Kata kunci penemuan (bobot)</div>
          <div className="flex flex-wrap gap-1">
            {kw.map((k, i) => (
              <span key={k.term} className="inline-flex items-center gap-1 rounded border border-line2 bg-bg/60 px-1.5 py-0.5 text-2xs">
                {k.term}
                <button className="font-mono text-dim hover:text-teal" disabled={!editable} title="Ubah bobot"
                  onClick={() => setKw(kw.map((x, j) => (j === i ? { ...x, weight: x.weight >= 1 ? 0.4 : 1 } : x)))}>{k.weight}</button>
                {editable && <button onClick={() => setKw(kw.filter((_, j) => j !== i))} className="text-dim hover:text-danger"><X className="h-3 w-3" /></button>}
              </span>
            ))}
          </div>
          {editable && (
            <div className="mt-2 flex gap-1.5">
              <Input placeholder="tambah istilah / ejaan varian…" value={term} onChange={(e) => setTerm(e.target.value)} className="h-7"
                onKeyDown={(e) => { if (e.key === "Enter" && term.trim()) { setKw([...kw, { term: term.trim().toLowerCase(), weight: 1 }]); setTerm(""); } }} />
              <Button size="sm" variant="secondary" disabled={!term.trim()} onClick={() => { setKw([...kw, { term: term.trim().toLowerCase(), weight: 1 }]); setTerm(""); }}><Plus /></Button>
              <Button size="sm" disabled={!dirty || busy} onClick={save}><Save />Simpan (versi baru)</Button>
            </div>
          )}
          {err && <div className="mt-1"><ErrorBox>{err}</ErrorBox></div>}
        </div>
        <details className="text-2xs text-mute">
          <summary className="cursor-pointer text-dim hover:text-ink">Aturan klasifikasi kontekstual ({c.context_rules.length})</summary>
          <ul className="mt-1 space-y-0.5 pl-3">{c.context_rules.map((r: any) => <li key={r.rule}><span className="font-mono text-dim">{r.rule}</span> — {r.description}</li>)}</ul>
        </details>
      </div>
    </Card>
  );
}

function ReviewQueue() {
  const { meta, can } = useApp();
  const [status, setStatus] = useState("belum_ditinjau");
  const [cat, setCat] = useState("");
  const [ctx, setCtx] = useState("");
  const [page, setPage] = useState(0);
  const { data, error, loading, reload } = useApi<any>(`/api/classifications${qs({ status, category: cat, context: ctx, limit: 25, offset: page * 25 })}`);
  const [notes, setNotes] = useState<Record<number, string>>({});
  useEffect(() => setPage(0), [status, cat, ctx]);
  async function decide(id: number, decision: string) {
    await api(`/api/classifications/${id}/review`, { method: "POST", body: JSON.stringify({ decision, note: notes[id] || null }) });
    reload();
  }
  return (
    <Card>
      <CardHeader title="Antrean tinjauan manusia" subtitle="Validasi label mesin. Tolak bila konteks tidak memenuhi kriteria inklusi (mis. candaan, berita, edukasi)."
        right={<div className="flex gap-2">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            {["belum_ditinjau", "valid", "ditolak", "direvisi", "semua"].map((s) => <option key={s} value={s}>{VALIDATION_LABELS[s] || "Semua"}</option>)}
          </Select>
          <Select value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">Semua kategori</option>
            {meta?.categories.map((c) => <option key={c.code} value={c.code}>{c.code} {c.name}</option>)}
          </Select>
          <Select value={ctx} onChange={(e) => setCtx(e.target.value)}>
            <option value="">Semua konteks</option>
            {Object.entries(CONTEXT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </div>} />
      {error && <div className="p-4"><ErrorBox>{error}</ErrorBox></div>}
      {loading && !data && <div className="p-4"><Spinner /></div>}
      {data && (
        <div className="divide-y divide-line">
          {data.items.length === 0 && <div className="p-4"><Empty>Tidak ada item.</Empty></div>}
          {data.items.map((r: any) => (
            <div key={r.id} className="grid gap-3 p-3 text-xs lg:grid-cols-[1fr_300px]">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-mono text-ink">{r.content_code}</span>
                  <span className="text-2xs text-dim">{PLATFORM_NAMES[r.platform]} · {fmtDateTime(r.published_at)}</span>
                  <Badge color={meta?.categories.find((c) => c.code === r.category)?.color}>{r.category}</Badge>
                  <Badge color={CONTEXT_COLORS[r.context_label]}>{CONTEXT_LABELS[r.context_label]}</Badge>
                  <span className="font-mono text-2xs text-teal">keyakinan {r.confidence.toFixed(2)}</span>
                  <Badge color="#64748B">{r.model_version}</Badge>
                </div>
                <p className="mt-1.5 rounded border border-line bg-bg/50 p-2 leading-relaxed">{r.text}</p>
                <p className="mt-1 text-2xs text-dim">{r.rationale}</p>
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <span className="label-xs">Status</span>
                  <Badge color={r.validation_status === "valid" ? "#2DD4BF" : r.validation_status === "ditolak" ? "#F87171" : "#94A3B8"}>{VALIDATION_LABELS[r.validation_status]}</Badge>
                </div>
                {can("validate") ? (
                  <>
                    <Input placeholder="Catatan peninjau (opsional)" value={notes[r.id] ?? r.reviewer_note ?? ""} onChange={(e) => setNotes({ ...notes, [r.id]: e.target.value })} className="h-7" />
                    <div className="flex gap-1.5">
                      <Button size="sm" onClick={() => decide(r.id, "valid")}><Check />Valid</Button>
                      <Button size="sm" variant="danger" onClick={() => decide(r.id, "ditolak")}><X />Tolak</Button>
                      <Button size="sm" variant="secondary" onClick={() => decide(r.id, "direvisi")}>Revisi</Button>
                    </div>
                  </>
                ) : <p className="text-2xs text-dim">Peran Anda tidak memiliki izin validasi.</p>}
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between p-3 text-2xs text-mute">
            <span>{data.total} item</span>
            <div className="flex gap-1.5">
              <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>Sebelumnya</Button>
              <Button size="sm" variant="secondary" disabled={(page + 1) * 25 >= data.total} onClick={() => setPage(page + 1)}>Berikutnya</Button>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

const SAMPLES = [
  "meniru gaya jalan orang pincang biar viral wkwk, ketawain bareng",
  "ini gak lucu. jangan ketawain disabilitas orang, hargai sesama",
  "berita: polisi mengamankan pelajar yang hendak tawuran, menurut keterangan kepolisian",
  "sl0t gac0rrr malam ini, depo 10rb auto maxwin link di bio",
];

function TestClassifier() {
  const { meta } = useApp();
  const [text, setText] = useState(SAMPLES[0]);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  async function run() {
    setErr(null);
    try {
      setRes(await api("/api/classify/test", { method: "POST", body: JSON.stringify({ text }) }));
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader title="Uji pipeline klasifikasi" subtitle="Normalisasi teks Indonesia (slang, ejaan, leetspeak) → deteksi konteks → multi-label. Hasil uji tidak disimpan." />
        <div className="space-y-2 p-4">
          <Textarea rows={5} value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex flex-wrap gap-1">
            {SAMPLES.map((s) => <button key={s} onClick={() => setText(s)} className="rounded border border-line2 px-1.5 py-0.5 text-2xs text-mute hover:text-ink">{s.slice(0, 34)}…</button>)}
          </div>
          <Button onClick={run} disabled={!text.trim()}><Sparkles />Klasifikasi</Button>
          {err && <ErrorBox>{err}</ErrorBox>}
        </div>
      </Card>
      <Card>
        <CardHeader title="Hasil" subtitle={res ? `Model ${res.model_version}` : undefined} />
        <div className="space-y-3 p-4 text-xs">
          {!res ? <Empty>Jalankan klasifikasi untuk melihat hasil.</Empty> : (
            <>
              <div><div className="label-xs mb-1">Teks ternormalisasi</div><code className="block rounded bg-bg/70 p-2 text-2xs text-cyan">{res.normalized_text}</code></div>
              <div className="flex items-center gap-2"><span className="label-xs">Konteks</span><Badge color={CONTEXT_COLORS[res.context_label]}>{CONTEXT_LABELS[res.context_label]}</Badge>
                {res.context_markers.length > 0 && <span className="text-2xs text-dim">penanda: {res.context_markers.join(", ")}</span>}</div>
              {res.labels.length === 0 ? <Empty>Tidak ada kategori yang terdeteksi.</Empty> : res.labels.map((l: any) => (
                <div key={l.code} className="rounded-md border border-line bg-bg/40 p-2.5">
                  <div className="flex items-center gap-2">
                    <Dot color={meta?.categories.find((c) => c.code === l.code)?.color || "#fff"} />
                    <span className="font-mono">{l.code}</span><span>{meta?.categories.find((c) => c.code === l.code)?.name}</span>
                    <span className="ml-auto font-mono text-teal">{l.confidence.toFixed(3)}</span>
                  </div>
                  <p className="mt-1 text-2xs text-dim">{l.rationale}</p>
                </div>
              ))}
              <Notice>{res.note}</Notice>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}

function KeywordDiscovery() {
  const { meta, can } = useApp();
  const { data, error, reload } = useApi<any>("/api/keywords/discover");
  const cats = useApi<any[]>("/api/categories");
  async function accept(code: string, term: string) {
    const c = cats.data?.find((x) => x.code === code);
    if (!c) return;
    await api(`/api/categories/${code}`, { method: "PATCH", body: JSON.stringify({ keywords: [...c.keywords, { term, weight: 0.5 }] }) });
    cats.reload();
    reload();
  }
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return <Spinner />;
  return (
    <div className="space-y-3">
      <Notice>{data.note} Skor = log-odds kemunculan istilah pada konten kandidat kategori dibandingkan seluruh korpus.</Notice>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Object.entries(data.suggestions as Record<string, any[]>).map(([code, list]) => (
          <Card key={code}>
            <CardHeader title={<span className="flex items-center gap-2"><Dot color={meta?.categories.find((c) => c.code === code)?.color || "#fff"} />{code}</span>}
              subtitle={meta?.categories.find((c) => c.code === code)?.name} />
            <div className="space-y-1 p-3">
              {list.length === 0 && <Empty>Belum ada usulan.</Empty>}
              {list.map((s) => (
                <div key={s.term} className="flex items-center gap-2 text-xs">
                  <span className="font-mono">{s.term}</span>
                  <span className="text-2xs text-dim">skor {s.score} · df {s.doc_freq}</span>
                  {can("edit_taxonomy") && <button onClick={() => accept(code, s.term)} className="ml-auto text-2xs text-teal hover:underline">terima</button>}
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

function Similarity() {
  const [code, setCode] = useState("ABL-C1");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  async function run() {
    setErr(null);
    try {
      const g = await api<any>(`/api/graph${qs({ layer: "konten" })}`);
      const node = g.nodes.find((n: any) => n.label.toLowerCase() === code.trim().toLowerCase());
      if (!node) throw new Error("Kode konten tidak ditemukan pada graf difusi. Coba kode ABL-…, TTG-…, atau JDL-…");
      setRes(await api(`/api/content/${node.id.slice(1)}/similar?threshold=0.4`));
    } catch (e) {
      setErr((e as Error).message);
    }
  }
  return (
    <Card>
      <CardHeader title="Kandidat konten serupa" subtitle="Kemiripan n-gram karakter + token (tahan variasi ejaan). Kemiripan BUKAN bukti peniruan." />
      <div className="space-y-3 p-4">
        <div className="flex max-w-md gap-2">
          <Input value={code} onChange={(e) => setCode(e.target.value)} placeholder="Kode konten, mis. ABL-C1" />
          <Button onClick={run}>Cari</Button>
        </div>
        {err && <ErrorBox>{err}</ErrorBox>}
        {res && (
          <>
            <Notice tone="warn">{res.note}</Notice>
            <table className="w-full text-xs">
              <thead className="label-xs text-left"><tr><th className="py-1.5">Kode</th><th>Platform</th><th>Terbit</th><th>Kemiripan</th><th>Urutan</th><th>Teks</th></tr></thead>
              <tbody className="divide-y divide-line">
                {res.candidates.map((c: any) => (
                  <tr key={c.id}>
                    <td className="py-1.5 font-mono">{c.code}</td><td>{PLATFORM_NAMES[c.platform]}</td><td className="text-mute">{fmtDateTime(c.published_at)}</td>
                    <td className="font-mono text-teal">{c.similarity.toFixed(2)}</td>
                    <td>{c.after_base ? <Badge color="#94A3B8">setelah</Badge> : <Badge color="#FBBF24">sebelum</Badge>}{c.same_actor && <Badge color="#A78BFA" className="ml-1">aktor sama</Badge>}</td>
                    <td className="max-w-md truncate text-mute">{c.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </Card>
  );
}
