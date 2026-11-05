"use client";

import { useState } from "react";
import { Page } from "@/components/layout/Page";
import { Badge, Bar, Card, CardHeader, Dot, ErrorBox, Notice, PageHeader, Spinner, Stat, Tabs } from "@/components/ui/primitives";
import { qs } from "@/lib/api";
import { ACCOUNT_LABELS, communityColor, CONTEXT_COLORS, CONTEXT_LABELS, fmtNum, PLATFORM_COLORS, PLATFORM_NAMES } from "@/lib/format";
import { useApi, useApp, useFilterParams } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Communities() {
  const { meta } = useApp();
  const fp = useFilterParams();
  const [layer, setLayer] = useState<"aktor" | "konten" | "bipartit">("aktor");
  const { data, error, loading } = useApi<any>(`/api/communities${qs({ ...fp, layer })}`);
  const catColor = (c: string) => meta?.categories.find((x) => x.code === c)?.color || "#94A3B8";

  return (
    <Page>
      <PageHeader title="Deteksi Komunitas" subtitle="Komunitas berbasis modularitas (Louvain) pada lapisan jaringan terpilih."
        right={<Tabs value={layer} onChange={setLayer} items={[{ value: "aktor", label: "Aktor–Aktor" }, { value: "konten", label: "Difusi Konten" }, { value: "bipartit", label: "Aktor–Konten" }]} />} />
      {error && <ErrorBox>{error}</ErrorBox>}
      {loading && !data && <Spinner />}
      {data && (
        <div className="space-y-4">
          <Card className="grid grid-cols-2 gap-4 p-4 md:grid-cols-5">
            <Stat label="Modularitas" value={data.modularity?.toFixed(3)} accent="#A78BFA" hint="Q > 0,3 umumnya menandakan struktur komunitas yang jelas." />
            <Stat label="Komunitas" value={data.communities.length} />
            <Stat label="Node" value={fmtNum(data.summary.nodes)} />
            <Stat label="Densitas" value={data.summary.density.toFixed(4)} />
            <Stat label="Komponen lemah" value={data.summary.weak_components} />
          </Card>
          <Notice>{data.note} Metode: {data.method}</Notice>
          <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {data.communities.map((c: any) => {
                const catMax = Math.max(1, ...Object.values(c.categories as Record<string, number>));
                return (
                  <Card key={c.id}>
                    <CardHeader title={<span className="flex items-center gap-2"><Dot color={communityColor(c.id)} size={10} />Komunitas {c.id + 1}</span>}
                      subtitle={`${c.size} node · densitas internal ${c.internal_density.toFixed(3)} · bobot internal/eksternal ${c.internal_weight}/${c.external_weight}`} />
                    <div className="space-y-3 p-3 text-xs">
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(c.platforms as Record<string, number>).map(([p, n]) => <Badge key={p} color={PLATFORM_COLORS[p]}>{PLATFORM_NAMES[p]} {n}</Badge>)}
                        {Object.entries((c.account_categories || {}) as Record<string, number>).slice(0, 3).map(([k, n]) => <Badge key={k} color="#94A3B8">{ACCOUNT_LABELS[k] || k} {n}</Badge>)}
                      </div>
                      <div>
                        <div className="label-xs mb-1">Kategori dominan</div>
                        {Object.entries(c.categories as Record<string, number>).slice(0, 4).map(([k, v]) => (
                          <div key={k} className="mb-1"><div className="flex justify-between text-2xs"><span className="font-mono">{k}</span><span className="font-mono text-mute">{v}</span></div>
                            <Bar value={v} max={catMax} color={catColor(k)} /></div>
                        ))}
                        {Object.keys(c.categories).length === 0 && <div className="text-2xs text-dim">—</div>}
                      </div>
                      {c.contexts && Object.keys(c.contexts).length > 0 && (
                        <div className="flex flex-wrap gap-1">{Object.entries(c.contexts as Record<string, number>).map(([k, v]) => <Badge key={k} color={CONTEXT_COLORS[k]}>{CONTEXT_LABELS[k]} {v}</Badge>)}</div>
                      )}
                      <div>
                        <div className="label-xs mb-1">Node penghubung (betweenness tertinggi)</div>
                        <div className="flex flex-wrap gap-1">{c.bridge_nodes.map((b: any) => <span key={b.id} className="rounded bg-bg/60 px-1.5 py-0.5 font-mono text-2xs">{b.label} <span className="text-dim">{b.betweenness.toFixed(3)}</span></span>)}</div>
                      </div>
                    </div>
                  </Card>
                );
              })}
            </div>
            <Card className="h-fit">
              <CardHeader title="Keterhubungan antarkomunitas" subtitle="Bobot interaksi lintas komunitas (arah sumber → target)." />
              <div className="space-y-1 p-3">
                {data.inter_community.length === 0 && <div className="text-2xs text-dim">Tidak ada edge lintas komunitas.</div>}
                {data.inter_community.slice(0, 24).map((e: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <Dot color={communityColor(e.source)} /><span className="w-8 font-mono">{e.source + 1}</span>→
                    <Dot color={communityColor(e.target)} /><span className="w-8 font-mono">{e.target + 1}</span>
                    <div className="flex-1"><Bar value={e.weight} max={data.inter_community[0].weight} color="#60A5FA" /></div>
                    <span className="w-8 text-right font-mono text-mute">{e.weight}</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </Page>
  );
}
