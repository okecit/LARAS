"use client";

import {
  Crosshair, Download, Expand, FileImage, Maximize2, Minus, Plus, RefreshCw, Route, SlidersHorizontal, X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CytoGraph, type ColorMode, type CytoHandle } from "@/components/graph/CytoGraph";
import { NodePanel } from "@/components/graph/NodePanel";
import { Button } from "@/components/ui/button";
import { Badge, Dot, ErrorBox, Hint, Select, Spinner, Stat, Switch, Tabs } from "@/components/ui/primitives";
import { api, download, qs, saveBlob } from "@/lib/api";
import {
  cn, communityColor, CONTEXT_COLORS, CONTEXT_LABELS, EVIDENCE_COLORS, EVIDENCE_LABELS, fmtNum, INTERACTION_LABELS, PLATFORM_COLORS, PLATFORM_NAMES,
} from "@/lib/format";
import { useApp, useFilterParams } from "@/lib/store";
import type { GEdge, GNode, GraphResponse, MetricKey } from "@/lib/types";

type Layer = "aktor" | "konten" | "bipartit";
const METRICS: { value: MetricKey; label: string }[] = [
  { value: "pagerank", label: "PageRank" }, { value: "in_degree", label: "In-degree" }, { value: "out_degree", label: "Out-degree" },
  { value: "betweenness", label: "Betweenness" }, { value: "closeness", label: "Closeness" }, { value: "degree", label: "Derajat berbobot" },
];
const LAYER_INTERACTIONS: Record<Layer, string[]> = {
  aktor: ["komentar", "balasan", "bagikan", "kutipan", "remix", "sebutan"],
  bipartit: ["membuat", "komentar", "balasan", "bagikan", "kutipan", "remix"],
  konten: [],
};

export default function NetworkExplorer() {
  const { meta, filters, can } = useApp();
  const fp = useFilterParams();
  const graphRef = useRef<CytoHandle>(null);
  const [layer, setLayer] = useState<Layer>("aktor");
  const [sizeMetric, setSizeMetric] = useState<MetricKey>("pagerank");
  const [colorMode, setColorMode] = useState<ColorMode>("komunitas");
  const [minWeight, setMinWeight] = useState(1);
  const [itypes, setItypes] = useState<string[]>([]);
  const [evStatuses, setEvStatuses] = useState<string[]>([]);
  const [includeSim, setIncludeSim] = useState(true);
  const [data, setData] = useState<GraphResponse | null>(null);
  const [extra, setExtra] = useState<{ nodes: GNode[]; edges: GEdge[] }>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ id: string; kind: "node" | "edge" } | null>(null);
  const [pathEnds, setPathEnds] = useState<{ source?: string; target?: string }>({});
  const [path, setPath] = useState<{ path: string[]; note: string | null; directed: boolean } | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [temporal, setTemporal] = useState<{ date: string; content: number; interactions: number; harmful: number; counter: number }[]>([]);

  const params = useMemo(() => ({
    layer, ...fp, interaction_types: itypes, evidence_statuses: evStatuses, min_weight: minWeight, include_similarity: includeSim,
  }), [layer, fp, itypes, evStatuses, minWeight, includeSim]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    api<GraphResponse>(`/api/graph${qs(params)}`)
      .then((d) => {
        if (!alive) return;
        setData(d);
        setExtra({ nodes: [], edges: [] });
        setPath(null);
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [params]);

  useEffect(() => {
    api<{ daily: typeof temporal }>(`/api/sna/temporal${qs({ ...fp, interaction_types: layer === "aktor" ? itypes : [] })}`)
      .then((d) => setTemporal(d.daily))
      .catch(() => setTemporal([]));
  }, [fp, itypes, layer]);

  useEffect(() => {
    setItypes([]);
    setSelected(null);
    setPathEnds({});
    if (layer === "konten") setColorMode((c) => (c === "komunitas" ? "konteks" : c));
  }, [layer]);

  const nodes = useMemo(() => {
    if (!data) return [];
    const ids = new Set(data.nodes.map((n) => n.id));
    return [...data.nodes, ...extra.nodes.filter((n) => !ids.has(n.id))];
  }, [data, extra]);
  const edges = useMemo(() => {
    if (!data) return [];
    const ids = new Set(nodes.map((n) => n.id));
    const keys = new Set(data.edges.map((e) => `${e.source}>${e.target}`));
    return [...data.edges, ...extra.edges.filter((e) => !keys.has(`${e.source}>${e.target}`) && ids.has(e.source) && ids.has(e.target))];
  }, [data, extra, nodes]);
  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const catColors = useMemo(() => Object.fromEntries((meta?.categories || []).map((c) => [c.code, c.color])), [meta]);

  const onSelect = useCallback((id: string | null, kind: "node" | "edge" | null) => setSelected(id && kind ? { id, kind } : null), []);

  const expand = useCallback(async (id: string) => {
    try {
      const d = await api<{ nodes: GNode[]; edges: GEdge[] }>(`/api/graph/expand${qs({ node_id: id, layer })}`);
      setExtra((prev) => ({ nodes: [...prev.nodes, ...d.nodes], edges: [...prev.edges, ...d.edges] }));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [layer]);

  async function findPath(source: string, target: string) {
    const r = await api<{ path: string[]; note: string | null; directed: boolean }>(`/api/graph/path${qs({ ...params, source, target })}`);
    setPath(r);
  }

  useEffect(() => {
    if (pathEnds.source && pathEnds.target) findPath(pathEnds.source, pathEnds.target).catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathEnds]);

  function exportPng() {
    const uri = graphRef.current?.png();
    if (!uri) return;
    fetch(uri).then((r) => r.blob()).then((b) => saveBlob(b, `laras_${layer}_${meta?.data_mode}.png`));
  }

  const selectedEdge = selected?.kind === "edge" ? edges.find((e) => e.id === selected.id) : undefined;
  const s = data?.summary;

  return (
    <div className="flex h-full flex-col">
      <div className="flex min-h-0 flex-1">
        {/* ------------------------------------------------ kanvas graf */}
        <section className="relative min-w-0 flex-1 grid-bg">
          <div className="absolute left-3 right-3 top-3 z-10 flex flex-wrap items-center gap-2">
            <Tabs value={layer} onChange={setLayer} items={[
              { value: "aktor", label: "Aktor–Aktor" }, { value: "konten", label: "Difusi Konten" }, { value: "bipartit", label: "Aktor–Konten" },
            ]} />
            <div className="flex items-center gap-1.5 rounded-md border border-line bg-bg/80 px-2 py-1">
              <span className="label-xs">Ukuran</span>
              <Select value={sizeMetric} onChange={(e) => setSizeMetric(e.target.value as MetricKey)} className="h-6 border-0 bg-transparent px-1">
                {METRICS.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
              </Select>
              {meta?.metrics[sizeMetric] && <Hint text={meta.metrics[sizeMetric].explanation} />}
            </div>
            <div className="flex items-center gap-1.5 rounded-md border border-line bg-bg/80 px-2 py-1">
              <span className="label-xs">Warna</span>
              <Select value={colorMode} onChange={(e) => setColorMode(e.target.value as ColorMode)} className="h-6 border-0 bg-transparent px-1">
                <option value="komunitas">Komunitas (Louvain)</option>
                <option value="platform">Platform</option>
                <option value="kategori">Kategori utama</option>
                {layer !== "aktor" && <option value="konteks">Konteks konten</option>}
              </Select>
            </div>
            <Button variant={showFilters ? "default" : "secondary"} size="sm" onClick={() => setShowFilters(!showFilters)}>
              <SlidersHorizontal /> Filter lanjutan
              {(itypes.length + evStatuses.length > 0 || minWeight > 1) && <Badge color="#FBBF24">aktif</Badge>}
            </Button>
            <div className="ml-auto flex items-center gap-1">
              {loading && <Spinner label="Menghitung metrik…" />}
            </div>
          </div>

          {showFilters && (
            <div className="absolute left-3 top-14 z-10 w-80 space-y-3 rounded-lg border border-line2 bg-panel/95 p-3 shadow-2xl backdrop-blur">
              <div>
                <div className="label-xs mb-1 flex items-center justify-between">
                  <span>Ambang bobot edge</span><span className="font-mono text-teal">≥ {minWeight}</span>
                </div>
                <input type="range" min={1} max={6} step={1} value={minWeight} onChange={(e) => setMinWeight(Number(e.target.value))} className="w-full"
                  disabled={layer === "konten"} />
                <p className="text-2xs text-dim">Bobot = jumlah interaksi terdokumentasi antara dua node.</p>
              </div>
              {LAYER_INTERACTIONS[layer].length > 0 && (
                <div>
                  <div className="label-xs mb-1">Jenis interaksi</div>
                  <div className="flex flex-wrap gap-1">
                    {LAYER_INTERACTIONS[layer].map((t) => (
                      <button key={t} onClick={() => setItypes(itypes.includes(t) ? itypes.filter((x) => x !== t) : [...itypes, t])}
                        className={cn("rounded border px-2 py-0.5 text-2xs", itypes.includes(t) ? "border-teal text-teal" : "border-line2 text-mute")}>
                        {INTERACTION_LABELS[t]}
                      </button>
                    ))}
                  </div>
                  <p className="mt-1 text-2xs text-dim">Kosong = semua jenis.</p>
                </div>
              )}
              {layer === "konten" && (
                <div className="space-y-2">
                  <div className="label-xs">Status bukti</div>
                  <div className="flex flex-wrap gap-1">
                    {Object.keys(EVIDENCE_LABELS).map((st) => (
                      <button key={st} onClick={() => setEvStatuses(evStatuses.includes(st) ? evStatuses.filter((x) => x !== st) : [...evStatuses, st])}
                        className={cn("flex items-center gap-1 rounded border px-2 py-0.5 text-2xs", evStatuses.includes(st) ? "border-teal text-ink" : "border-line2 text-mute")}>
                        <Dot color={EVIDENCE_COLORS[st]} size={6} />{EVIDENCE_LABELS[st]}
                      </button>
                    ))}
                  </div>
                  <Switch checked={includeSim} onChange={setIncludeSim} label="Tampilkan relasi kemiripan (garis putus-putus)" />
                </div>
              )}
              <Button variant="ghost" size="sm" onClick={() => { setItypes([]); setEvStatuses([]); setMinWeight(1); setIncludeSim(true); }}>
                Atur ulang filter
              </Button>
            </div>
          )}

          {error && <div className="absolute left-3 top-14 z-20"><ErrorBox>{error}</ErrorBox></div>}

          {data && nodes.length === 0 && !loading && (
            <div className="absolute inset-0 flex items-center justify-center text-xs text-dim">Tidak ada node yang cocok dengan filter saat ini.</div>
          )}
          <CytoGraph ref={graphRef} nodes={nodes} edges={edges} sizeMetric={sizeMetric} colorMode={colorMode} categoryColors={catColors}
            selectedId={selected?.id ?? null} pathIds={path?.path ?? []} search={filters.search} onSelect={onSelect} onNodeDoubleClick={expand} />

          <div className="absolute bottom-3 left-3 z-10 flex flex-col gap-1">
            <IconBtn title="Perbesar" onClick={() => graphRef.current?.zoom(1.3)}><Plus /></IconBtn>
            <IconBtn title="Perkecil" onClick={() => graphRef.current?.zoom(0.77)}><Minus /></IconBtn>
            <IconBtn title="Paskan ke layar" onClick={() => graphRef.current?.fit()}><Maximize2 /></IconBtn>
            <IconBtn title="Tata letak ulang (force-directed)" onClick={() => graphRef.current?.relayout()}><RefreshCw /></IconBtn>
          </div>

          <Legend layer={layer} colorMode={colorMode} data={data} />

          {(pathEnds.source || path) && (
            <div className="absolute bottom-3 left-14 z-10 max-w-md rounded-lg border border-cyan/40 bg-panel/95 p-2.5 text-2xs shadow-xl">
              <div className="mb-1 flex items-center gap-2 font-semibold text-cyan">
                <Route className="h-3.5 w-3.5" /> Jalur terpendek
                <button className="ml-auto text-dim hover:text-ink" onClick={() => { setPathEnds({}); setPath(null); }}><X className="h-3.5 w-3.5" /></button>
              </div>
              <div className="text-mute">
                Asal: <b className="text-ink">{pathEnds.source ? nodeById.get(pathEnds.source)?.label : "—"}</b> · Tujuan:{" "}
                <b className="text-ink">{pathEnds.target ? nodeById.get(pathEnds.target)?.label : "pilih node lalu klik “Jadikan tujuan”"}</b>
              </div>
              {path && (path.path.length ? (
                <div className="mt-1 font-mono text-ink">
                  {path.path.map((p) => nodeById.get(p)?.label || p).join(" → ")}{" "}
                  <span className="text-dim">({path.path.length - 1} langkah{path.directed ? ", terarah" : ", diabaikan arah"})</span>
                </div>
              ) : <div className="mt-1 text-amber">{path.note}</div>)}
            </div>
          )}
        </section>

        {/* ------------------------------------------------ panel kanan */}
        <aside className="w-[350px] shrink-0 overflow-y-auto border-l border-line bg-panel/70">
          {selected?.kind === "node" && nodeById.get(selected.id) ? (
            <NodePanel node={nodeById.get(selected.id)!} sizeMetric={sizeMetric} onClose={() => setSelected(null)}
              onExpand={() => expand(selected.id)} onFocus={(id) => { setSelected({ id, kind: "node" }); graphRef.current?.focus(id); }}
              onPathSource={() => { setPathEnds({ source: selected.id }); setPath(null); }}
              onPathTarget={() => setPathEnds((p) => ({ ...p, target: selected.id }))} canPathTarget={!!pathEnds.source && pathEnds.source !== selected.id} />
          ) : selectedEdge ? (
            <EdgePanel edge={selectedEdge} nodeById={nodeById} onClose={() => setSelected(null)} />
          ) : (
            <OverviewPanel data={data} onFocus={(id) => { setSelected({ id, kind: "node" }); graphRef.current?.focus(id); }} sizeMetric={sizeMetric} />
          )}
        </aside>
      </div>

      {/* ------------------------------------------------ panel bawah */}
      <div className="grid h-[178px] shrink-0 grid-cols-[1fr_auto_auto] gap-0 border-t border-line bg-panel/80">
        <div className="min-w-0 px-4 py-2.5">
          <div className="mb-1 flex items-center gap-3">
            <span className="label-xs">Aktivitas temporal (harian)</span>
            <LegendDot color="#22D3EE" label="Konten" /><LegendDot color="#A78BFA" label="Interaksi" />
            <LegendDot color="#F87171" label="Kandidat berbahaya" /><LegendDot color="#2DD4BF" label="Kontra-narasi/edukasi/berita" />
          </div>
          <div className="h-[132px]">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={temporal} margin={{ top: 4, right: 4, bottom: 0, left: -24 }}>
                <CartesianGrid stroke="#1E2A44" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: "#64748B", fontSize: 10 }} tickFormatter={(d: string) => d.slice(5)} minTickGap={28} />
                <YAxis tick={{ fill: "#64748B", fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#0F172A", border: "1px solid #2A3A5C", fontSize: 11 }} />
                <Area type="monotone" dataKey="interactions" name="Interaksi" stroke="#A78BFA" fill="#A78BFA" fillOpacity={0.15} strokeWidth={1.5} />
                <Area type="monotone" dataKey="content" name="Konten" stroke="#22D3EE" fill="#22D3EE" fillOpacity={0.12} strokeWidth={1.5} />
                <Area type="monotone" dataKey="harmful" name="Kandidat berbahaya" stroke="#F87171" fill="none" strokeWidth={1.2} />
                <Area type="monotone" dataKey="counter" name="Kontra/edukasi/berita" stroke="#2DD4BF" fill="none" strokeWidth={1.2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="grid w-[380px] grid-cols-3 content-center gap-x-4 gap-y-3 border-l border-line px-4">
          <Stat label="Node" value={fmtNum(s?.nodes)} />
          <Stat label="Edge" value={fmtNum(s?.edges)} />
          <Stat label="Densitas" value={s ? s.density.toFixed(4) : "—"} hint="Proporsi edge yang ada dari semua edge yang mungkin." />
          <Stat label="Komponen lemah" value={fmtNum(s?.weak_components)} />
          <Stat label="Modularitas" value={s?.modularity?.toFixed(3) ?? "—"} accent="#A78BFA" hint="Kekuatan pembagian komunitas Louvain (0–1)." />
          <Stat label="Komponen terbesar" value={s ? `${Math.round(s.largest_component_share * 100)}%` : "—"} accent="#2DD4BF" />
        </div>
        <div className="flex w-[250px] flex-col justify-center gap-1.5 border-l border-line px-4">
          <span className="label-xs">Ekspor graf ({meta?.layers[layer]})</span>
          {can("export") ? (
            <>
              <div className="grid grid-cols-2 gap-1.5">
                {[["graphml", "GraphML"], ["gexf", "GEXF"], ["csv_nodes", "CSV node"], ["csv_edges", "CSV edge"]].map(([f, l]) => (
                  <Button key={f} variant="secondary" size="sm"
                    onClick={() => download(`/api/graph/export${qs({ ...params, format: f })}`, `laras.${f}`).catch((e) => setError(e.message))}>
                    <Download />{l}
                  </Button>
                ))}
              </div>
              <Button variant="secondary" size="sm" onClick={exportPng}><FileImage />PNG (tampilan saat ini)</Button>
            </>
          ) : <p className="text-2xs text-dim">Peran Anda tidak memiliki izin ekspor.</p>}
          <p className="text-2xs text-dim">Ekspor memakai pseudonim; tercatat di log audit.</p>
        </div>
      </div>
    </div>
  );
}

function IconBtn({ children, title, onClick }: { children: React.ReactNode; title: string; onClick: () => void }) {
  return (
    <button title={title} onClick={onClick}
      className="flex h-8 w-8 items-center justify-center rounded-md border border-line2 bg-panel/90 text-mute hover:border-teal/60 hover:text-teal [&_svg]:h-4 [&_svg]:w-4">
      {children}
    </button>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return <span className="flex items-center gap-1 text-2xs text-mute"><Dot color={color} size={6} />{label}</span>;
}

function Legend({ layer, colorMode, data }: { layer: Layer; colorMode: ColorMode; data: GraphResponse | null }) {
  const { meta } = useApp();
  let items: { color: string; label: string }[] = [];
  if (colorMode === "komunitas") items = (data?.communities || []).slice(0, 8).map((c) => ({ color: communityColor(c.id), label: `Kom. ${c.id + 1} · ${c.size}` }));
  if (colorMode === "platform") items = Object.entries(PLATFORM_NAMES).filter(([k]) => k !== "lainnya").map(([k, v]) => ({ color: PLATFORM_COLORS[k], label: v }));
  if (colorMode === "kategori") items = (meta?.categories || []).map((c) => ({ color: c.color, label: c.code }));
  if (colorMode === "konteks") items = Object.entries(CONTEXT_LABELS).slice(0, 7).map(([k, v]) => ({ color: CONTEXT_COLORS[k], label: v }));
  return (
    <div className="absolute bottom-3 right-3 z-10 max-w-[380px] rounded-lg border border-line bg-panel/90 p-2.5 text-2xs backdrop-blur">
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {items.map((i) => <LegendDot key={i.label} {...i} />)}
      </div>
      {layer === "konten" && (
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-1.5">
          {Object.entries(EVIDENCE_LABELS).map(([k, v]) => (
            <span key={k} className="flex items-center gap-1 text-mute">
              <span className="inline-block h-0.5 w-4" style={{ background: EVIDENCE_COLORS[k], borderTop: k === "kemiripan" ? "1px dashed #94A3B8" : undefined }} />{v}
            </span>
          ))}
        </div>
      )}
      <div className="mt-1.5 flex items-center gap-1 border-t border-line pt-1.5 text-dim">
        <Crosshair className="h-3 w-3" /> Klik = detail · klik ganda = perluas tetangga · {layer !== "aktor" ? "kotak = konten, " : ""}ukuran = metrik
      </div>
    </div>
  );
}

function EdgePanel({ edge, nodeById, onClose }: { edge: GEdge; nodeById: Map<string, GNode>; onClose: () => void }) {
  const s = nodeById.get(edge.source), t = nodeById.get(edge.target);
  return (
    <div className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <div><div className="label-xs">Edge terpilih</div><div className="font-mono text-sm">{s?.label} → {t?.label}</div></div>
        <button onClick={onClose} className="text-dim hover:text-ink"><X className="h-4 w-4" /></button>
      </div>
      <div className="space-y-2 text-xs">
        <Row k="Bobot" v={fmtNum(edge.weight)} />
        <Row k="Jenis" v={edge.types.map((t) => INTERACTION_LABELS[t] || t).join(", ")} />
        {edge.evidence_status && <Row k="Status bukti" v={<Badge color={EVIDENCE_COLORS[edge.evidence_status]}>{EVIDENCE_LABELS[edge.evidence_status]}</Badge>} />}
        {edge.confidence !== undefined && <Row k="Keyakinan" v={edge.confidence.toFixed(2)} />}
        {edge.documented !== undefined && <Row k="Didokumentasikan platform" v={edge.documented ? "Ya" : "Tidak"} />}
      </div>
      {edge.similarity_only && (
        <p className="mt-3 rounded border border-line2 p-2 text-2xs text-mute">
          Relasi ini hanya kemiripan. Kemiripan bukan bukti transmisi atau peniruan.
        </p>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex items-center justify-between gap-2 border-b border-line/60 pb-1.5"><span className="text-mute">{k}</span><span className="text-right">{v}</span></div>;
}

function OverviewPanel({ data, onFocus, sizeMetric }: { data: GraphResponse | null; onFocus: (id: string) => void; sizeMetric: MetricKey }) {
  const { meta } = useApp();
  if (!data) return <div className="p-4"><Spinner /></div>;
  const s = data.summary;
  const topNodes = [...data.nodes].sort((a, b) => (b.metrics[sizeMetric] ?? 0) - (a.metrics[sizeMetric] ?? 0)).slice(0, 6);
  return (
    <div className="space-y-4 p-4">
      <div>
        <div className="label-xs">Ringkasan jaringan</div>
        <div className="mt-2 grid grid-cols-3 gap-3">
          <Stat label="Resiprositas" value={s.reciprocity.toFixed(2)} />
          <Stat label="Komunitas" value={fmtNum(s.communities)} accent="#A78BFA" />
          <Stat label="Komp. kuat" value={fmtNum(s.strong_components)} />
        </div>
      </div>
      <div>
        <div className="label-xs mb-2">Komunitas (modularitas {s.modularity?.toFixed(3)})</div>
        <div className="space-y-1.5">
          {data.communities.slice(0, 8).map((c) => (
            <div key={c.id} className="rounded-md border border-line bg-bg/40 px-2.5 py-1.5">
              <div className="flex items-center gap-2 text-xs">
                <Dot color={communityColor(c.id)} />
                <span className="font-medium">Komunitas {c.id + 1}</span>
                <span className="ml-auto font-mono text-2xs text-mute">{c.size} node · ρ {c.internal_density.toFixed(2)}</span>
              </div>
              <div className="mt-1 flex flex-wrap gap-1">
                {Object.entries(c.categories).slice(0, 3).map(([k, v]) => (
                  <Badge key={k} color={meta?.categories.find((x) => x.code === k)?.color}>{k} · {v}</Badge>
                ))}
                {Object.entries(c.platforms).slice(0, 2).map(([k, v]) => <Badge key={k} color={PLATFORM_COLORS[k]}>{PLATFORM_NAMES[k]} {v}</Badge>)}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="label-xs mb-2 flex items-center gap-1">Posisi struktural tertinggi · {meta?.metrics[sizeMetric]?.label}
          <Hint text="Daftar ini untuk navigasi graf, bukan peringkat individu. Posisi jaringan bukan ukuran pengaruh atau kesalahan." /></div>
        <div className="space-y-1">
          {topNodes.map((n) => (
            <button key={n.id} onClick={() => onFocus(n.id)} className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-xs hover:bg-panel2">
              <Dot color={communityColor(n.community)} />
              <span className="font-mono">{n.label}</span>
              <span className="text-2xs text-dim">{PLATFORM_NAMES[n.platform]}</span>
              <span className="ml-auto font-mono text-2xs text-mute">{(n.metrics[sizeMetric] ?? 0).toFixed(4)}</span>
            </button>
          ))}
        </div>
      </div>
      <p className="rounded-md border border-amber/25 bg-amber/5 p-2.5 text-2xs leading-relaxed text-amber/90">
        <Expand className="mr-1 inline h-3 w-3" />{data.disclaimer}
      </p>
    </div>
  );
}
