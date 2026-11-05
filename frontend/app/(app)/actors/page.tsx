"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Page } from "@/components/layout/Page";
import { Badge, Card, CardHeader, Dot, ErrorBox, Hint, Input, Notice, PageHeader, Select, Spinner } from "@/components/ui/primitives";
import { qs } from "@/lib/api";
import { ACCOUNT_LABELS, communityColor, CONTEXT_COLORS, CONTEXT_LABELS, fmtMetric, PLATFORM_COLORS, PLATFORM_NAMES } from "@/lib/format";
import { useApi, useApp, useFilterParams } from "@/lib/store";
import type { MetricKey } from "@/lib/types";

/* eslint-disable @typescript-eslint/no-explicit-any */
const COLS: MetricKey[] = ["in_degree", "out_degree", "betweenness", "closeness", "pagerank"];

export default function ActorAnalytics() {
  const { meta } = useApp();
  const fp = useFilterParams();
  const { data, error, loading } = useApi<any>(`/api/actors${qs({ ...fp })}`);
  const [sort, setSort] = useState<string>("pseudonym");
  const [acct, setAcct] = useState("");
  const [q, setQ] = useState("");
  const [hist, setHist] = useState<MetricKey>("pagerank");

  const rows = useMemo(() => {
    if (!data) return [];
    let r = data.actors.filter((a: any) => (!acct || a.account_category === acct) && (!q || a.pseudonym.toLowerCase().includes(q.toLowerCase())));
    r = [...r].sort((a: any, b: any) => sort === "pseudonym" ? a.pseudonym.localeCompare(b.pseudonym)
      : sort === "community" ? a.community - b.community : (b.metrics[sort] ?? 0) - (a.metrics[sort] ?? 0));
    return r;
  }, [data, sort, acct, q]);

  const histogram = useMemo(() => {
    if (!data) return [];
    const vals = data.actors.map((a: any) => a.metrics[hist] ?? 0);
    const max = Math.max(...vals, 1e-9);
    const bins = Array.from({ length: 12 }, (_, i) => ({ bin: `${((i / 12) * max).toFixed(3)}`, n: 0 }));
    vals.forEach((v: number) => bins[Math.min(11, Math.floor((v / max) * 12))].n++);
    return bins;
  }, [data, hist]);

  return (
    <Page>
      <PageHeader title="Actor Analytics" subtitle="Analitik posisi jaringan aktor berpseudonim pada jaringan interaksi aktor–aktor (mengikuti filter periode, platform, dan kategori)." />
      <Notice tone="warn">
        Ini bukan papan peringkat. Tidak ada label pelaku, inferensi usia, identitas, atau kondisi psikologis. Kategori akun hanya
        berasal dari metadata publik (mis. akun media). {data?.disclaimer}
      </Notice>
      {error && <div className="mt-3"><ErrorBox>{error}</ErrorBox></div>}
      {loading && !data && <div className="mt-3"><Spinner /></div>}
      {data && (
        <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
          <Card>
            <CardHeader title={`Aktor (${rows.length})`} right={
              <div className="flex gap-2">
                <Input placeholder="Cari pseudonim" value={q} onChange={(e) => setQ(e.target.value)} className="w-40" />
                <Select value={acct} onChange={(e) => setAcct(e.target.value)}>
                  <option value="">Semua jenis akun</option>
                  {Object.entries(ACCOUNT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
                <Select value={sort} onChange={(e) => setSort(e.target.value)}>
                  <option value="pseudonym">Urut: pseudonim</option>
                  <option value="community">Urut: komunitas</option>
                  {COLS.map((c) => <option key={c} value={c}>Urut: {meta?.metrics[c]?.label}</option>)}
                </Select>
              </div>} />
            <div className="max-h-[calc(100vh-260px)] overflow-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-panel">
                  <tr className="label-xs text-left">
                    <th className="px-3 py-2">Pseudonim</th><th>Platform</th><th>Jenis akun</th><th>Komunitas</th>
                    {COLS.map((c) => <th key={c} className="text-right"><span className="inline-flex items-center gap-1">{meta?.metrics[c]?.label.replace("Sentralitas ", "")}<Hint text={meta?.metrics[c]?.explanation || ""} /></span></th>)}
                    <th className="px-3">Konteks konten</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line/60">
                  {rows.map((a: any) => (
                    <tr key={a.id} className="hover:bg-panel2/50">
                      <td className="px-3 py-1.5 font-mono">{a.pseudonym}</td>
                      <td><span className="flex items-center gap-1"><Dot color={PLATFORM_COLORS[a.platform]} size={6} />{PLATFORM_NAMES[a.platform]}</span></td>
                      <td className="text-mute">{ACCOUNT_LABELS[a.account_category]}</td>
                      <td><span className="flex items-center gap-1"><Dot color={communityColor(a.community)} size={7} />{a.community + 1}</span></td>
                      {COLS.map((c) => <td key={c} className={`text-right font-mono ${sort === c ? "text-teal" : "text-mute"}`}>{fmtMetric(a.metrics[c])}</td>)}
                      <td className="px-3">
                        <div className="flex gap-0.5">
                          {Object.entries(a.contexts as Record<string, number>).map(([k, v]) => (
                            <span key={k} title={`${CONTEXT_LABELS[k]}: ${v}`} className="h-2 rounded-sm" style={{ width: 6 * v, background: CONTEXT_COLORS[k] }} />
                          ))}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <div className="space-y-4">
            <Card>
              <CardHeader title="Distribusi metrik" subtitle="Histogram lebih informatif daripada peringkat individu." right={
                <Select value={hist} onChange={(e) => setHist(e.target.value as MetricKey)}>
                  {COLS.map((c) => <option key={c} value={c}>{meta?.metrics[c]?.label}</option>)}
                </Select>} />
              <div className="h-48 p-2">
                <ResponsiveContainer>
                  <BarChart data={histogram}>
                    <CartesianGrid stroke="#1E2A44" vertical={false} />
                    <XAxis dataKey="bin" tick={{ fill: "#64748B", fontSize: 9 }} />
                    <YAxis tick={{ fill: "#64748B", fontSize: 10 }} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: "#0F172A", border: "1px solid #2A3A5C", fontSize: 11 }} />
                    <Bar dataKey="n" name="Aktor" fill="#2DD4BF" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="grid grid-cols-3 gap-2 border-t border-line p-3 text-2xs">
                {(["min", "median", "max"] as const).map((k) => (
                  <div key={k}><div className="text-dim">{k}</div><div className="font-mono">{fmtMetric(data.distribution[hist]?.[k])}</div></div>
                ))}
              </div>
            </Card>
            <Card>
              <CardHeader title="Jenis akun (metadata publik)" />
              <div className="flex flex-wrap gap-1.5 p-3">
                {Object.entries(data.account_categories as Record<string, number>).map(([k, v]) => <Badge key={k} color="#94A3B8">{ACCOUNT_LABELS[k] || k} · {v}</Badge>)}
              </div>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
