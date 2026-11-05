"use client";

import { AlertTriangle, Flag, GitBranch, Info, Plus } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge, Card, Dot, Empty, ErrorBox, Input, Notice, Select, Spinner, Switch } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import {
  CONTEXT_COLORS, CONTEXT_LABELS, EVIDENCE_COLORS, EVIDENCE_LABELS, fmtDateTime, fmtHours, fmtNum, PLATFORM_COLORS, PLATFORM_NAMES, RELATION_LABELS,
} from "@/lib/format";
import { useApi, useApp } from "@/lib/store";
import { useTheme } from "@/lib/theme";

/* eslint-disable @typescript-eslint/no-explicit-any */
const LANES = ["tiktok", "instagram", "x", "youtube", "lainnya"];
const EV_TYPES = ["atribusi_eksplisit", "metadata_platform", "kemiripan_teks", "kemiripan_visual", "audio_sama", "tagar_tren", "urutan_waktu",
  "perilaku_sebelumnya", "celah_data", "catatan_peneliti"];

export default function DiffusionTracker() {
  const cases = useApi<any[]>("/api/diffusion/cases");
  const [caseId, setCaseId] = useState<string | null>(null);
  const [includeSim, setIncludeSim] = useState(true);
  const [tick, setTick] = useState(0);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<{ type: "node" | "edge"; id: string | number } | null>(null);

  useEffect(() => {
    if (!caseId && cases.data?.length) setCaseId(cases.data[0].id);
  }, [cases.data, caseId]);
  useEffect(() => {
    if (!caseId) return;
    setErr(null);
    api<any>(`/api/diffusion/cascade/${caseId}?include_similarity=${includeSim}`).then(setData).catch((e) => setErr(e.message));
  }, [caseId, includeSim, tick]);
  useEffect(() => setSel(null), [caseId]);

  const nodeById = useMemo(() => new Map<string, any>((data?.nodes || []).map((n: any) => [n.id, n])), [data]);
  const selNode = sel?.type === "node" ? nodeById.get(sel.id as string) : null;
  const selEdge = sel?.type === "edge" ? data?.edges.find((e: any) => e.id === sel.id) : null;

  return (
    <div className="flex h-full">
      <aside className="w-64 shrink-0 overflow-y-auto border-r border-line bg-panel/60 p-3">
        <div className="label-xs mb-2">Kasus kaskade</div>
        {cases.loading && <Spinner />}
        {cases.data?.map((c) => (
          <button key={c.id} onClick={() => setCaseId(c.id)}
            className={`mb-1.5 block w-full rounded-md border p-2.5 text-left text-xs transition-colors ${caseId === c.id ? "border-teal/60 bg-teal/5" : "border-line hover:border-line2"}`}>
            <div className="flex items-center gap-1.5"><GitBranch className="h-3.5 w-3.5 text-teal" /><span className="font-mono text-2xs text-mute">{c.id}</span>
              {c.is_scenario && <Badge color="#FBBF24" className="ml-auto">DEMO</Badge>}</div>
            <div className="mt-1 font-medium leading-snug">{c.title}</div>
            <div className="mt-1 flex flex-wrap gap-1">{c.platforms.map((p: string) => <Dot key={p} color={PLATFORM_COLORS[p]} size={7} />)}
              <span className="text-2xs text-dim">{c.size} konten · {c.dominant_categories.join(", ")}</span></div>
          </button>
        ))}
        <div className="mt-4 space-y-1.5 border-t border-line pt-3">
          <div className="label-xs">Status bukti</div>
          {Object.entries(EVIDENCE_LABELS).map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-2xs text-mute">
              <svg width="22" height="6"><line x1="0" y1="3" x2="22" y2="3" stroke={EVIDENCE_COLORS[k]} strokeWidth="2" strokeDasharray={k === "kemiripan" ? "3 3" : undefined} /></svg>{v}
            </div>
          ))}
          <p className="pt-1 text-2xs leading-relaxed text-dim">Kemiripan saja tidak pernah diperlakukan sebagai transmisi. Status hanya dapat dinaikkan bila bukti mendukung.</p>
        </div>
      </aside>

      <section className="min-w-0 flex-1 overflow-y-auto">
        <div className="p-4">
          {err && <ErrorBox>{err}</ErrorBox>}
          {!data && !err && <Spinner />}
          {data && (
            <>
              <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <h1 className="text-lg font-semibold">{data.case.title}</h1>
                  <p className="text-xs text-mute">Lini masa terobservasi per platform. Sumbu X = waktu terbit (WIB); ukuran = tayangan; warna node = konteks; warna garis = status bukti.</p>
                </div>
                <Switch checked={includeSim} onChange={setIncludeSim} label="Tampilkan relasi kemiripan" />
              </div>
              <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-6">
                <SumBox k="Pertama teramati" v={nodeById.get(data.summary.first_observed_id)?.code} sub={fmtDateTime(data.summary.first_observed_at)} accent="#FBBF24" />
                <SumBox k="Akar transmisi" v={data.nodes.filter((n: any) => n.is_transmission_root).map((n: any) => n.code).join(", ") || "—"} sub="memiliki turunan berbukti" accent="#2DD4BF" />
                <SumBox k="Rentang waktu" v={fmtHours(data.summary.span_hours)} sub={`${data.summary.items} konten`} />
                <SumBox k="Relasi transmisi" v={`${data.summary.transmission_relations} / ${data.summary.relations}`} sub="berbukti / total" />
                <SumBox k="Kedalaman maks." v={data.summary.max_depth} sub="langkah transmisi" />
                <SumBox k="Urutan platform" v={data.summary.platforms_sequence.map((p: string) => PLATFORM_NAMES[p]).join(" → ")} sub="pertama teramati per platform" />
              </div>
              <Card className="p-2">
                <Cascade data={data} selected={sel} onSelect={setSel} />
              </Card>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <Card className="p-3">
                  <div className="label-xs mb-2 flex items-center gap-1"><AlertTriangle className="h-3 w-3 text-amber" />Indikator ketidakpastian</div>
                  <div className="space-y-1.5">
                    {data.uncertainties.map((u: any, i: number) => (
                      <div key={i} className={`flex gap-2 text-2xs leading-relaxed ${u.level === "peringatan" ? "text-amber/90" : "text-mute"}`}>
                        {u.level === "peringatan" ? <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" /> : <Info className="mt-0.5 h-3 w-3 shrink-0" />}{u.message}
                      </div>
                    ))}
                    {data.content_evidence.map((e: any, i: number) => (
                      <div key={`c${i}`} className="flex gap-2 text-2xs text-mute"><Flag className="mt-0.5 h-3 w-3 shrink-0 text-cyan" />
                        <span><span className="font-mono">{nodeById.get(e.content_id)?.code}</span> · {e.description}</span></div>
                    ))}
                  </div>
                </Card>
                <Card className="p-3">
                  <div className="label-xs mb-2">Konten pertama teramati vs pencipta asli</div>
                  <p className="text-2xs leading-relaxed text-mute">{data.summary.originator_note}</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {Object.entries(data.summary.status_counts as Record<string, number>).map(([k, v]) => <Badge key={k} color={EVIDENCE_COLORS[k]}>{EVIDENCE_LABELS[k]} · {v}</Badge>)}
                  </div>
                </Card>
              </div>
            </>
          )}
        </div>
      </section>

      <aside className="w-[340px] shrink-0 overflow-y-auto border-l border-line bg-panel/70 p-4 text-xs">
        {selNode ? <NodeInfo n={selNode} data={data} onSelect={setSel} /> : selEdge ? (
          <EdgeEvidence e={selEdge} nodeById={nodeById} onChanged={() => setTick((t) => t + 1)} />
        ) : (
          <div className="space-y-3">
            <div className="label-xs">Panel bukti</div>
            <Empty>Klik node (konten) atau garis (relasi) pada kaskade untuk melihat bukti pendukung dan bertentangan.</Empty>
            <Notice>Garis hanya digambar bila ada metadata platform, atribusi eksplisit, atau catatan peneliti. Tautan difusi tidak dibuat bila data platform tidak tersedia.</Notice>
          </div>
        )}
      </aside>
    </div>
  );
}

function SumBox({ k, v, sub, accent }: { k: string; v: React.ReactNode; sub?: string; accent?: string }) {
  return (
    <div className="rounded-md border border-line bg-panel/70 px-2.5 py-2">
      <div className="label-xs truncate">{k}</div>
      <div className="mt-0.5 truncate font-mono text-sm font-semibold" style={accent ? { color: accent } : undefined}>{v}</div>
      {sub && <div className="truncate text-2xs text-dim">{sub}</div>}
    </div>
  );
}

function Cascade({ data, selected, onSelect }: { data: any; selected: any; onSelect: (s: any) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(900);
  const { palette } = useTheme();
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((e) => setW(e[0].contentRect.width));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  const lanes = LANES.filter((l) => data.nodes.some((n: any) => n.platform === l));
  const laneH = 118, padL = 92, padR = 30, top = 26;
  const H = top + lanes.length * laneH + 28;
  const times = data.nodes.map((n: any) => new Date(n.published_at).getTime());
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const span = Math.max(t1 - t0, 3600e3);
  const x = (t: number) => padL + ((t - t0) / span) * (w - padL - padR);
  const maxViews = Math.max(1, ...data.nodes.map((n: any) => n.metrics?.tayangan || 0));
  const pos = new Map<string, { x: number; y: number; r: number }>();
  const laneCount: Record<string, number> = {};
  for (const n of [...data.nodes].sort((a: any, b: any) => a.order - b.order)) {
    const li = lanes.indexOf(n.platform);
    const k = (laneCount[n.platform] = (laneCount[n.platform] ?? -1) + 1);
    const offs = [0, -30, 30, -15, 15, -42, 42][k % 7];
    const r = n.content_type === "komentar" ? 4 : 6 + Math.sqrt((n.metrics?.tayangan || 0) / maxViews) * 14;
    pos.set(n.id, { x: x(new Date(n.published_at).getTime()), y: top + li * laneH + laneH / 2 + offs, r });
  }
  const ticks = Array.from({ length: 7 }, (_, i) => t0 + (span * i) / 6);
  const dfmt = new Intl.DateTimeFormat("id-ID", { day: "2-digit", month: "short", timeZone: "Asia/Jakarta" });
  return (
    <div ref={ref} className="w-full">
      <svg width={w} height={H} className="block">
        <defs>
          {Object.entries(EVIDENCE_COLORS).map(([k, c]) => (
            <marker key={k} id={`arr-${k}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={c} />
            </marker>
          ))}
        </defs>
        {lanes.map((l, i) => (
          <g key={l}>
            <rect x={0} y={top + i * laneH} width={w} height={laneH} fill={i % 2 ? palette.laneB : palette.laneA} />
            <text className="tone" x={10} y={top + i * laneH + laneH / 2 + 4} fill={PLATFORM_COLORS[l]} fontSize={11} fontWeight={600}>{PLATFORM_NAMES[l]}</text>
          </g>
        ))}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={top} y2={H - 24} stroke={palette.line} strokeDasharray="2 4" />
            <text x={x(t)} y={H - 8} fill={palette.dim} fontSize={10} textAnchor="middle">{dfmt.format(new Date(t))}</text>
          </g>
        ))}
        {data.edges.map((e: any) => {
          const a = pos.get(e.source), b = pos.get(e.target);
          if (!a || !b) return null;
          const isSel = selected?.type === "edge" && selected.id === e.id;
          const mx = (a.x + b.x) / 2, my = Math.min(a.y, b.y) - 18 - Math.abs(a.x - b.x) * 0.06;
          const dx = b.x - mx, dy = b.y - my, len = Math.hypot(dx, dy) || 1;
          const ex = b.x - (dx / len) * (b.r + 2), ey = b.y - (dy / len) * (b.r + 2);
          const isComment = nodeOf(data, e.target)?.content_type === "komentar";
          return (
            <path key={e.id} d={`M ${a.x} ${a.y} Q ${mx} ${my} ${ex} ${ey}`} fill="none" stroke={EVIDENCE_COLORS[e.evidence_status]}
              strokeWidth={isSel ? 3.5 : isComment ? 0.8 : 1.8} strokeOpacity={isSel ? 1 : isComment ? 0.35 : 0.85}
              strokeDasharray={e.evidence_status === "kemiripan" ? "4 4" : e.evidence_status === "kemungkinan_replikasi" ? "8 3" : undefined}
              markerEnd={e.evidence_status === "kemiripan" ? undefined : `url(#arr-${e.evidence_status})`}
              className="cursor-pointer" onClick={() => onSelect({ type: "edge", id: e.id })}>
              <title>{`${RELATION_LABELS[e.relation_type]} · ${EVIDENCE_LABELS[e.evidence_status]}`}</title>
            </path>
          );
        })}
        {data.nodes.map((n: any) => {
          const p = pos.get(n.id)!;
          const isSel = selected?.type === "node" && selected.id === n.id;
          return (
            <g key={n.id} className="cursor-pointer" onClick={() => onSelect({ type: "node", id: n.id })}>
              {n.is_first_observed && <circle cx={p.x} cy={p.y} r={p.r + 6} fill="none" stroke="#FBBF24" strokeDasharray="3 2" />}
              {n.is_transmission_root && <circle cx={p.x} cy={p.y} r={p.r + 5} fill="none" stroke="#2DD4BF" strokeWidth={1.5} />}
              <circle cx={p.x} cy={p.y} r={p.r} fill={CONTEXT_COLORS[n.context_label] || "#64748B"} fillOpacity={0.9}
                stroke={isSel ? palette.highlight : palette.nodeBorder} strokeWidth={isSel ? 2.5 : 1} />
              {n.content_type !== "komentar" && (
                <text x={p.x} y={p.y - p.r - 5} fill={palette.label} fontSize={9.5} textAnchor="middle" className="pointer-events-none select-none font-mono">
                  {n.code.replace(/^[A-Z]+-/, "")}
                </text>
              )}
              <title>{`${n.code} · ${CONTEXT_LABELS[n.context_label]} · ${fmtDateTime(n.published_at)}`}</title>
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap gap-x-4 gap-y-1 px-2 pb-1 text-2xs text-mute">
        <span className="flex items-center gap-1"><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="none" stroke="#FBBF24" strokeDasharray="3 2" /></svg>Pertama teramati</span>
        <span className="flex items-center gap-1"><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="none" stroke="#2DD4BF" strokeWidth="1.5" /></svg>Akar transmisi berbukti</span>
        {["kandidat_berbahaya", "kontra_narasi", "edukasi", "berita", "pencegahan", "satire"].map((k) => (
          <span key={k} className="flex items-center gap-1"><Dot color={CONTEXT_COLORS[k]} size={7} />{CONTEXT_LABELS[k]}</span>
        ))}
      </div>
    </div>
  );
}

function nodeOf(data: any, id: string) {
  return data.nodes.find((n: any) => n.id === id);
}

function NodeInfo({ n, data, onSelect }: { n: any; data: any; onSelect: (s: any) => void }) {
  const { meta } = useApp();
  const rels = data.edges.filter((e: any) => e.source === n.id || e.target === n.id);
  return (
    <div className="space-y-3">
      <div>
        <div className="font-mono text-sm font-semibold">{n.code}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          <Badge color={PLATFORM_COLORS[n.platform]}>{PLATFORM_NAMES[n.platform]}</Badge>
          <Badge color={CONTEXT_COLORS[n.context_label]}>{CONTEXT_LABELS[n.context_label]}</Badge>
          {n.is_first_observed && <Badge color="#FBBF24">Pertama teramati</Badge>}
          {n.is_transmission_root && <Badge color="#2DD4BF">Akar transmisi</Badge>}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-2xs">
        <div><div className="text-dim">Terbit</div>{fmtDateTime(n.published_at)}</div>
        <div><div className="text-dim">Sejak pertama teramati</div>{fmtHours(n.hours_since_first)}</div>
        <div><div className="text-dim">Aktor (pseudonim)</div><span className="font-mono">{n.actor}</span></div>
        <div><div className="text-dim">Tayangan</div>{fmtNum(n.metrics?.tayangan || 0)}</div>
      </div>
      <p className="rounded-md border border-line bg-bg/50 p-2.5 leading-relaxed">{n.text}</p>
      <div className="flex flex-wrap gap-1">{n.categories.map((c: string) => <Badge key={c} color={meta?.categories.find((x) => x.code === c)?.color}>{c}</Badge>)}</div>
      <div>
        <div className="label-xs mb-1">Relasi</div>
        {rels.map((e: any) => {
          const other = nodeOf(data, e.source === n.id ? e.target : e.source);
          return (
            <button key={e.id} onClick={() => onSelect({ type: "edge", id: e.id })} className="mb-1 flex w-full items-center gap-2 rounded border border-line px-2 py-1 text-left text-2xs hover:border-line2">
              <span>{e.source === n.id ? "→" : "←"}</span><span className="font-mono">{other?.code}</span>
              <Badge color={EVIDENCE_COLORS[e.evidence_status]} className="ml-auto">{EVIDENCE_LABELS[e.evidence_status]}</Badge>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function EdgeEvidence({ e, nodeById, onChanged }: { e: any; nodeById: Map<string, any>; onChanged: () => void }) {
  const { can } = useApp();
  const [form, setForm] = useState({ evidence_type: "catatan_peneliti", direction: "mendukung", strength: 0.5, description: "" });
  const [status, setStatus] = useState(e.evidence_status);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { setStatus(e.evidence_status); setMsg(null); setErr(null); }, [e]);
  const s = nodeById.get(e.source), t = nodeById.get(e.target);
  async function addEv() {
    setErr(null);
    try {
      const r = await api<any>(`/api/diffusion/relations/${e.id}/evidence`, { method: "POST", body: JSON.stringify(form) });
      setMsg(`Bukti ditambahkan. Status maksimum yang didukung: ${EVIDENCE_LABELS[r.max_supported_status]}.`);
      setForm({ ...form, description: "" });
      onChanged();
    } catch (x) { setErr((x as Error).message); }
  }
  async function setSt() {
    setErr(null);
    try {
      await api(`/api/diffusion/relations/${e.id}/status`, { method: "PATCH", body: JSON.stringify({ evidence_status: status }) });
      setMsg("Status diperbarui.");
      onChanged();
    } catch (x) { setErr((x as Error).message); }
  }
  return (
    <div className="space-y-3">
      <div>
        <div className="label-xs">Relasi #{e.id}</div>
        <div className="font-mono text-sm">{s?.code} → {t?.code}</div>
        <div className="mt-1 flex flex-wrap gap-1">
          <Badge color={EVIDENCE_COLORS[e.evidence_status]}>{EVIDENCE_LABELS[e.evidence_status]}</Badge>
          <Badge color="#94A3B8">{RELATION_LABELS[e.relation_type]}</Badge>
          <Badge color={e.documented ? "#2DD4BF" : "#64748B"}>{e.documented ? "metadata platform" : "tinjauan peneliti"}</Badge>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-2xs">
        <div><div className="text-dim">Keyakinan</div><span className="font-mono">{e.confidence.toFixed(2)}</span></div>
        <div><div className="text-dim">Jeda</div>{fmtHours(e.time_lag_hours)}</div>
        <div><div className="text-dim">Kemiripan teks</div><span className="font-mono">{e.similarity_score ?? "—"}</span></div>
      </div>
      {e.notes && <Notice tone="warn">{e.notes}</Notice>}
      <div>
        <div className="label-xs mb-1">Bukti ({e.supporting} mendukung · {e.contradicting} bertentangan)</div>
        {e.evidence.length === 0 && <Empty>Tidak ada catatan bukti terpisah{e.documented ? " — relasi tercatat di metadata platform" : ""}.</Empty>}
        {e.evidence.map((ev: any) => (
          <div key={ev.id} className="mb-1.5 rounded-md border border-line bg-bg/40 p-2">
            <div className="flex items-center gap-1.5 text-2xs">
              <Badge color={ev.direction === "mendukung" ? "#2DD4BF" : ev.direction === "bertentangan" ? "#F87171" : "#94A3B8"}>{ev.direction}</Badge>
              <span className="font-mono text-dim">{ev.type}</span><span className="ml-auto text-dim">{ev.strength}</span>
            </div>
            <p className="mt-1 text-2xs leading-relaxed text-mute">{ev.description}</p>
          </div>
        ))}
      </div>
      {can("edit_evidence") && (
        <div className="space-y-1.5 rounded-md border border-line p-2.5">
          <div className="label-xs">Tambah catatan bukti</div>
          <div className="grid grid-cols-2 gap-1.5">
            <Select value={form.evidence_type} onChange={(x) => setForm({ ...form, evidence_type: x.target.value })}>{EV_TYPES.map((t) => <option key={t}>{t}</option>)}</Select>
            <Select value={form.direction} onChange={(x) => setForm({ ...form, direction: x.target.value })}>
              <option value="mendukung">mendukung</option><option value="bertentangan">bertentangan</option><option value="netral">netral</option>
            </Select>
          </div>
          <Input placeholder="Deskripsi bukti (min. 5 karakter)" value={form.description} onChange={(x) => setForm({ ...form, description: x.target.value })} />
          <div className="flex items-center gap-2 text-2xs text-mute">Kekuatan
            <input type="range" min={0} max={1} step={0.1} value={form.strength} onChange={(x) => setForm({ ...form, strength: Number(x.target.value) })} className="flex-1" />
            <span className="font-mono">{form.strength}</span></div>
          <Button size="sm" onClick={addEv} disabled={form.description.length < 5}><Plus />Simpan bukti</Button>
        </div>
      )}
      {can("validate") && (
        <div className="space-y-1.5 rounded-md border border-line p-2.5">
          <div className="label-xs">Ubah status bukti (dibatasi oleh bukti)</div>
          <div className="flex gap-1.5">
            <Select value={status} onChange={(x) => setStatus(x.target.value)} className="flex-1">
              {Object.entries(EVIDENCE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Select>
            <Button size="sm" variant="secondary" onClick={setSt} disabled={status === e.evidence_status}>Terapkan</Button>
          </div>
        </div>
      )}
      {msg && <Notice>{msg}</Notice>}
      {err && <ErrorBox>{err}</ErrorBox>}
    </div>
  );
}
