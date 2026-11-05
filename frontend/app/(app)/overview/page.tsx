"use client";

import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Page } from "@/components/layout/Page";
import { Card, CardHeader, ErrorBox, Notice, PageHeader, Spinner, Stat } from "@/components/ui/primitives";
import { CONTEXT_COLORS, CONTEXT_LABELS, EVIDENCE_COLORS, EVIDENCE_LABELS, fmtNum, PLATFORM_COLORS, PLATFORM_NAMES, VALIDATION_LABELS } from "@/lib/format";
import { useApi, useApp } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
const TT = { contentStyle: { background: "#0F172A", border: "1px solid #2A3A5C", fontSize: 11 } };
const AX = { tick: { fill: "#64748B", fontSize: 10 } };

export default function OverviewPage() {
  const { meta } = useApp();
  const { data, error, loading } = useApi<any>("/api/overview");
  const cats = meta?.categories || [];

  return (
    <Page>
      <PageHeader title="Ikhtisar" subtitle="Ringkasan dataset, distribusi kategori, konteks, dan status validasi. Angka menggambarkan data yang terkumpul, bukan prevalensi populasi." />
      {error && <ErrorBox>{error}</ErrorBox>}
      {loading && <Spinner />}
      {data && (
        <div className="space-y-4">
          <Card className="grid grid-cols-3 gap-4 p-4 md:grid-cols-6">
            <Stat label="Konten" value={fmtNum(data.totals.contents)} accent="#22D3EE" />
            <Stat label="Aktor berpseudonim" value={fmtNum(data.totals.actors)} />
            <Stat label="Interaksi" value={fmtNum(data.totals.interactions)} accent="#A78BFA" />
            <Stat label="Relasi konten" value={fmtNum(data.totals.relations)} />
            <Stat label="Konten berlabel" value={fmtNum(data.totals.classified)} accent="#FBBF24" />
            <Stat label="Catatan bukti" value={fmtNum(data.totals.evidence)} accent="#2DD4BF" />
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Kategori × konteks" subtitle="Konten berlabel kategori dipisah menurut konteks: kandidat berbahaya vs kontra-narasi, berita, edukasi, satire, pencegahan." />
              <div className="h-72 p-3">
                <ResponsiveContainer>
                  <BarChart data={cats.map((c) => ({ code: c.code, ...(data.by_category_context[c.code] || {}) }))}>
                    <CartesianGrid stroke="#1E2A44" vertical={false} />
                    <XAxis dataKey="code" {...AX} />
                    <YAxis {...AX} />
                    <Tooltip {...TT} labelFormatter={(l) => `${l} — ${cats.find((c) => c.code === String(l))?.name ?? ""}`} />
                    <Legend wrapperStyle={{ fontSize: 11 }} formatter={(v: string) => CONTEXT_LABELS[v] || v} />
                    {["kandidat_berbahaya", "kontra_narasi", "edukasi", "berita", "pencegahan", "satire"].map((k) => (
                      <Bar key={k} dataKey={k} stackId="a" fill={CONTEXT_COLORS[k]} name={k} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <CardHeader title="Konteks seluruh konten" />
              <div className="h-72 p-3">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={Object.entries(data.by_context).map(([k, v]) => ({ name: CONTEXT_LABELS[k] || k, value: v, key: k }))}
                      dataKey="value" innerRadius={55} outerRadius={95} paddingAngle={2} stroke="none">
                      {Object.keys(data.by_context).map((k) => <Cell key={k} fill={CONTEXT_COLORS[k]} />)}
                    </Pie>
                    <Tooltip {...TT} />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader title="Tren mingguan per kategori" subtitle="Jumlah konten berlabel per minggu ISO." />
              <div className="h-64 p-3">
                <ResponsiveContainer>
                  <BarChart data={data.weekly}>
                    <CartesianGrid stroke="#1E2A44" vertical={false} />
                    <XAxis dataKey="week" {...AX} tickFormatter={(w: string) => w.slice(5)} />
                    <YAxis {...AX} />
                    <Tooltip {...TT} />
                    {cats.map((c) => <Bar key={c.code} dataKey={c.code} stackId="w" fill={c.color} />)}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <CardHeader title="Platform × kategori" />
              <div className="space-y-2 p-4">
                {Object.entries(data.by_platform as Record<string, number>).map(([p, n]) => (
                  <div key={p}>
                    <div className="flex justify-between text-xs"><span style={{ color: PLATFORM_COLORS[p] }}>{PLATFORM_NAMES[p]}</span><span className="font-mono text-mute">{fmtNum(n)} konten</span></div>
                    <div className="mt-1 flex h-2 overflow-hidden rounded-full bg-line">
                      {cats.map((c) => {
                        const v = data.by_platform_category[p]?.[c.code] || 0;
                        const total = Object.values(data.by_platform_category[p] || {}).reduce((a: number, b: any) => a + b, 0) as number;
                        return v ? <div key={c.code} title={`${c.code}: ${v}`} style={{ width: `${(v / total) * 100}%`, background: c.color }} /> : null;
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader title="Validasi manusia" subtitle="Label mesin wajib ditinjau sebelum dipakai dalam kesimpulan." />
              <div className="space-y-2 p-4">
                {Object.entries(data.validation as Record<string, number>).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between text-xs">
                    <span className="text-mute">{VALIDATION_LABELS[k] || k}</span><span className="font-mono">{fmtNum(v)}</span>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <CardHeader title="Status bukti relasi konten" />
              <div className="space-y-2 p-4">
                {Object.entries(EVIDENCE_LABELS).map(([k, l]) => (
                  <div key={k} className="flex items-center justify-between text-xs">
                    <span style={{ color: EVIDENCE_COLORS[k] }}>{l}</span><span className="font-mono">{fmtNum(data.evidence_status[k] || 0)}</span>
                  </div>
                ))}
              </div>
            </Card>
            <Card>
              <CardHeader title="Jaringan aktor (semua data)" />
              <div className="grid grid-cols-2 gap-3 p-4">
                <Stat label="Densitas" value={data.network.density.toFixed(4)} />
                <Stat label="Modularitas" value={data.network.modularity?.toFixed(3)} accent="#A78BFA" />
                <Stat label="Komponen lemah" value={data.network.weak_components} />
                <Stat label="Resiprositas" value={data.network.reciprocity.toFixed(2)} />
              </div>
            </Card>
          </div>
          <Notice>{meta?.disclaimer}</Notice>
        </div>
      )}
    </Page>
  );
}
