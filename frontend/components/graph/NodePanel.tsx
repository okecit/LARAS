"use client";

import { Expand, MapPin, Route, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar as RBar, BarChart, ResponsiveContainer, Tooltip, XAxis } from "recharts";
import { Button } from "@/components/ui/button";
import { Badge, Bar, Dot, Empty, ErrorBox, Hint, Spinner, Tabs, Textarea } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import {
  ACCOUNT_LABELS, communityColor, CONTEXT_COLORS, CONTEXT_LABELS, EVIDENCE_COLORS, EVIDENCE_LABELS, fmtDate, fmtDateTime, fmtHours, fmtMetric,
  INTERACTION_LABELS, PLATFORM_COLORS, PLATFORM_NAMES, RELATION_LABELS, VALIDATION_LABELS,
} from "@/lib/format";
import { useApp } from "@/lib/store";
import type { GNode, MetricKey } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
type Detail = any;

const METRIC_ORDER: MetricKey[] = ["pagerank", "in_degree", "out_degree", "betweenness", "closeness", "degree"];

export function NodePanel({ node, sizeMetric, onClose, onExpand, onFocus, onPathSource, onPathTarget, canPathTarget }: {
  node: GNode; sizeMetric: MetricKey; onClose: () => void; onExpand: () => void; onFocus: (id: string) => void;
  onPathSource: () => void; onPathTarget: () => void; canPathTarget: boolean;
}) {
  const { meta, can } = useApp();
  const [d, setD] = useState<Detail | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<"ringkasan" | "terhubung" | "linimasa" | "bukti">("ringkasan");
  const [note, setNote] = useState("");

  const load = () => api<Detail>(`/api/nodes/${node.id}`).then(setD).catch((e) => setErr(e.message));
  useEffect(() => {
    setD(null);
    setErr(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node.id]);

  async function addNote() {
    if (!d || note.trim().length < 3) return;
    await api("/api/annotations", { method: "POST", body: JSON.stringify({ target_type: d.kind, target_id: Number(node.id.slice(1)), body: note }) });
    setNote("");
    load();
  }

  const catName = (c: string) => meta?.categories.find((x) => x.code === c);
  const metricMax: Record<string, number> = { pagerank: 0.05, in_degree: 0.2, out_degree: 0.2, betweenness: 0.1, closeness: 0.5, degree: 40 };

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-line p-4">
        <div className="flex items-start gap-2">
          <Dot color={communityColor(node.community)} size={10} />
          <div className="min-w-0 flex-1">
            <div className="font-mono text-sm font-semibold">{node.label}</div>
            <div className="mt-0.5 flex flex-wrap items-center gap-1">
              <Badge color={PLATFORM_COLORS[node.platform]}>{PLATFORM_NAMES[node.platform]}</Badge>
              <Badge color="#94A3B8">{node.kind === "aktor" ? "Aktor berpseudonim" : "Konten"}</Badge>
              {node.community >= 0 && <Badge color={communityColor(node.community)}>Komunitas {node.community + 1}</Badge>}
              {node.scenario && <Badge color="#FBBF24">{node.scenario}</Badge>}
            </div>
          </div>
          <button onClick={onClose} className="text-dim hover:text-ink" title="Tutup"><X className="h-4 w-4" /></button>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Button size="sm" variant="secondary" onClick={onExpand} title="Tampilkan tetangga langsung tanpa filter kategori/waktu"><Expand />Perluas tetangga</Button>
          <Button size="sm" variant="secondary" onClick={onPathSource}><MapPin />Jadikan asal</Button>
          <Button size="sm" variant="secondary" onClick={onPathTarget} disabled={!canPathTarget}><Route />Jadikan tujuan</Button>
        </div>
      </div>
      <div className="border-b border-line px-4 py-2">
        <Tabs value={tab} onChange={setTab} items={[
          { value: "ringkasan", label: "Ringkasan" }, { value: "terhubung", label: "Terhubung" },
          { value: "linimasa", label: "Linimasa" }, { value: "bukti", label: "Bukti & catatan" },
        ]} />
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4 text-xs">
        {err && <ErrorBox>{err}</ErrorBox>}
        {!d && !err && <Spinner />}
        {d && tab === "ringkasan" && (
          <>
            <section>
              <div className="label-xs mb-2">Metrik interaksi (posisi jaringan)</div>
              <div className="space-y-1.5">
                {METRIC_ORDER.map((k) => (
                  <div key={k} className={k === sizeMetric ? "text-teal" : ""}>
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-1">{meta?.metrics[k]?.label}<Hint text={meta?.metrics[k]?.explanation || ""} /></span>
                      <span className="font-mono">{fmtMetric(node.metrics[k])}</span>
                    </div>
                    <Bar value={node.metrics[k] ?? 0} max={Math.max(metricMax[k], node.metrics[k] ?? 0)} color={k === sizeMetric ? "#2DD4BF" : "#3B4B6E"} />
                  </div>
                ))}
              </div>
            </section>
            {d.kind === "aktor" ? <ActorSummary d={d} catName={catName} /> : <ContentSummary d={d} catName={catName} canRaw={can("view_raw")} />}
          </>
        )}
        {d && tab === "terhubung" && (
          d.kind === "aktor" ? (
            <section className="space-y-1">
              <div className="label-xs mb-1">Node terhubung ({d.connected.length})</div>
              {d.connected.length === 0 && <Empty>Tidak ada interaksi terdokumentasi.</Empty>}
              {d.connected.map((c: any) => (
                <button key={c.id} onClick={() => onFocus(c.id)} className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left hover:bg-panel2">
                  <Dot color={PLATFORM_COLORS[c.platform]} size={7} />
                  <span className="font-mono">{c.label}</span>
                  <span className="truncate text-2xs text-dim">{Object.entries(c.types).map(([t, n]) => `${INTERACTION_LABELS[t] || t} ${n}`).join(" · ")}</span>
                  <span className="ml-auto whitespace-nowrap font-mono text-2xs text-mute">↗{c.out} ↙{c.in}</span>
                </button>
              ))}
            </section>
          ) : (
            <section className="space-y-1.5">
              <div className="label-xs mb-1">Relasi konten ({d.relations.length})</div>
              {d.relations.length === 0 && <Empty>Tidak ada relasi terdokumentasi.</Empty>}
              {d.relations.map((r: any) => (
                <button key={r.id} onClick={() => onFocus(r.other.id)} className="block w-full rounded-md border border-line bg-bg/40 px-2.5 py-1.5 text-left hover:border-line2">
                  <div className="flex items-center gap-2">
                    <span className="text-dim">{r.direction === "keluar" ? "→" : "←"}</span>
                    <span className="font-mono">{r.other.code}</span>
                    <span className="text-2xs text-dim">{PLATFORM_NAMES[r.other.platform]}</span>
                    <Badge color={EVIDENCE_COLORS[r.evidence_status]} className="ml-auto">{EVIDENCE_LABELS[r.evidence_status]}</Badge>
                  </div>
                  <div className="mt-0.5 text-2xs text-mute">{RELATION_LABELS[r.relation_type]} · jeda {fmtHours(r.time_lag_hours)} · {r.documented ? "metadata platform" : "tinjauan peneliti"}</div>
                </button>
              ))}
              <div className="pt-2"><button className="text-2xs text-mute hover:text-teal" onClick={() => onFocus(d.actor.id)}>Pembuat: <span className="font-mono">{d.actor.label}</span></button></div>
            </section>
          )
        )}
        {d && tab === "linimasa" && (
          <section>
            <div className="label-xs mb-2">Aktivitas per hari</div>
            {d.timeline.length === 0 ? <Empty>Tidak ada aktivitas.</Empty> : (
              <div className="h-32">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={d.timeline}>
                    <XAxis dataKey="date" tick={{ fill: "#64748B", fontSize: 9 }} tickFormatter={(x: string) => x.slice(5)} />
                    <Tooltip contentStyle={{ background: "#0F172A", border: "1px solid #2A3A5C", fontSize: 11 }} />
                    {d.kind === "aktor" && <RBar dataKey="content" name="Konten" fill="#22D3EE" />}
                    <RBar dataKey="interactions" name="Interaksi" fill="#A78BFA" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
            {d.kind === "aktor" && (
              <div className="mt-3 space-y-1.5">
                <div className="label-xs">Konten (terbaru 30)</div>
                {d.contents.slice().reverse().map((c: any) => (
                  <button key={c.id} onClick={() => onFocus(c.id)} className="block w-full rounded border border-line bg-bg/40 px-2 py-1.5 text-left hover:border-line2">
                    <div className="flex items-center gap-1.5 text-2xs">
                      <span className="font-mono text-ink">{c.code}</span>
                      <span className="text-dim">{fmtDateTime(c.published_at)}</span>
                      <Badge color={CONTEXT_COLORS[c.context_label]} className="ml-auto">{CONTEXT_LABELS[c.context_label]}</Badge>
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-2xs text-mute">{c.text}</div>
                  </button>
                ))}
              </div>
            )}
          </section>
        )}
        {d && tab === "bukti" && (
          <section className="space-y-3">
            <div>
              <div className="label-xs mb-1">Catatan bukti ({d.evidence.length})</div>
              {d.evidence.length === 0 && <Empty>Belum ada catatan bukti.</Empty>}
              {d.evidence.map((e: any) => (
                <div key={e.id} className="mb-1.5 rounded-md border border-line bg-bg/40 p-2">
                  <div className="flex items-center gap-1.5 text-2xs">
                    <Badge color={e.direction === "mendukung" ? "#2DD4BF" : e.direction === "bertentangan" ? "#F87171" : "#94A3B8"}>{e.direction}</Badge>
                    <span className="font-mono text-dim">{e.evidence_type}</span>
                    <span className="ml-auto text-dim">kekuatan {e.strength}</span>
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-mute">{e.description}</p>
                </div>
              ))}
            </div>
            <div>
              <div className="label-xs mb-1">Anotasi peneliti</div>
              {d.annotations.map((a: any) => (
                <div key={a.id} className="mb-1.5 rounded-md border border-line bg-bg/40 p-2 text-2xs text-mute">
                  <Badge color="#A78BFA">{a.kind}</Badge> {a.body}
                </div>
              ))}
              {can("annotate") && (
                <div className="mt-2 space-y-1.5">
                  <Textarea rows={2} placeholder="Tambahkan catatan analitis (bukan penilaian terhadap individu)…" value={note} onChange={(e) => setNote(e.target.value)} />
                  <Button size="sm" onClick={addNote} disabled={note.trim().length < 3}>Simpan catatan</Button>
                </div>
              )}
            </div>
          </section>
        )}
        {d?.note && <p className="text-2xs leading-relaxed text-dim">{d.note}</p>}
      </div>
    </div>
  );
}

function ActorSummary({ d, catName }: { d: Detail; catName: (c: string) => { name: string; color: string } | undefined }) {
  const cats = Object.entries(d.categories as Record<string, number>).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...cats.map(([, v]) => v));
  return (
    <>
      <section className="grid grid-cols-2 gap-2">
        <Info k="Jenis akun" v={ACCOUNT_LABELS[d.account_category] || d.account_category} />
        <Info k="Rentang pengikut" v={d.follower_bucket || "—"} />
        <Info k="Pertama teramati" v={fmtDate(d.first_seen_at)} />
        <Info k="Terakhir teramati" v={fmtDate(d.last_seen_at)} />
        <Info k="Interaksi keluar" v={d.interaction_totals.out} />
        <Info k="Interaksi masuk" v={d.interaction_totals.in} />
      </section>
      <section>
        <div className="label-xs mb-1.5">Kategori konten yang dibuat</div>
        {cats.length === 0 ? <Empty>Tidak ada konten berlabel.</Empty> : cats.map(([k, v]) => (
          <div key={k} className="mb-1.5">
            <div className="flex justify-between text-2xs"><span><span className="font-mono">{k}</span> {catName(k)?.name}</span><span className="font-mono">{v}</span></div>
            <Bar value={v} max={max} color={catName(k)?.color} />
          </div>
        ))}
      </section>
      <section>
        <div className="label-xs mb-1.5">Konteks konten</div>
        <div className="flex flex-wrap gap-1">
          {Object.entries(d.contexts as Record<string, number>).map(([k, v]) => <Badge key={k} color={CONTEXT_COLORS[k]}>{CONTEXT_LABELS[k]} · {v}</Badge>)}
        </div>
      </section>
    </>
  );
}

function ContentSummary({ d, catName, canRaw }: { d: Detail; catName: (c: string) => { name: string; color: string } | undefined; canRaw: boolean }) {
  return (
    <>
      <section className="grid grid-cols-2 gap-2">
        <Info k="Terbit" v={fmtDateTime(d.published_at)} />
        <Info k="Jenis" v={d.content_type} />
        <Info k="Konteks" v={<Badge color={CONTEXT_COLORS[d.context_label]}>{CONTEXT_LABELS[d.context_label]}</Badge>} />
        <Info k="Tayangan" v={(d.metrics?.tayangan ?? 0).toLocaleString("id-ID")} />
      </section>
      <section>
        <div className="label-xs mb-1 flex items-center gap-1">Kutipan teks {!canRaw && <Badge color="#FBBF24">dibatasi</Badge>}</div>
        <p className="rounded-md border border-line bg-bg/50 p-2.5 text-xs leading-relaxed">{d.text}</p>
      </section>
      <section>
        <div className="label-xs mb-1.5">Klasifikasi (multi-label)</div>
        {d.classifications.length === 0 && <Empty>Tidak ada label.</Empty>}
        {d.classifications.map((c: any) => (
          <div key={c.id} className="mb-1.5 rounded-md border border-line bg-bg/40 p-2">
            <div className="flex items-center gap-1.5">
              <Dot color={catName(c.code)?.color || "#fff"} />
              <span className="font-mono text-2xs">{c.code}</span>
              <span className="truncate text-2xs">{c.name}</span>
              <span className="ml-auto font-mono text-2xs text-teal">{c.confidence.toFixed(2)}</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-1 text-2xs">
              <Badge color={c.validation_status === "valid" ? "#2DD4BF" : c.validation_status === "ditolak" ? "#F87171" : "#94A3B8"}>
                {VALIDATION_LABELS[c.validation_status]}
              </Badge>
              <Badge color="#64748B">{c.model_version}</Badge>
            </div>
            <p className="mt-1 text-2xs text-dim">{c.rationale}</p>
          </div>
        ))}
      </section>
      <section className="text-2xs text-dim">
        Asal-usul: sumber #{d.provenance.source_id} · dikumpulkan {fmtDate(d.provenance.collected_at)} · akses {d.provenance.access_level}
        {d.provenance.generator ? ` · ${d.provenance.generator} (DEMO)` : ""}
      </section>
    </>
  );
}

function Info({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-bg/40 px-2 py-1.5">
      <div className="text-2xs text-dim">{k}</div>
      <div className="mt-0.5 truncate text-xs">{v}</div>
    </div>
  );
}
