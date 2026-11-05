"use client";

import { Check, Download, Save, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Page } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty, ErrorBox, Input, Notice, PageHeader, Select, Spinner, Switch, Tabs, Textarea } from "@/components/ui/primitives";
import { api, download, qs } from "@/lib/api";
import { EVIDENCE_COLORS, EVIDENCE_LABELS, fmtDate, fmtDateTime } from "@/lib/format";
import { useApi, useApp, useFilterParams } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
export default function Workspace() {
  const [tab, setTab] = useState<"etika" | "kesimpulan" | "bukti" | "ekspor">("etika");
  return (
    <Page>
      <PageHeader title="Ruang Kerja Riset" subtitle="Dokumentasi etika & persetujuan, anotasi, kesimpulan dengan tinjauan kedua, log bukti, retensi, dan ekspor hasil anonim." />
      <Tabs className="mb-4" value={tab} onChange={setTab} items={[
        { value: "etika", label: "Etika & data" }, { value: "kesimpulan", label: "Anotasi & kesimpulan" },
        { value: "bukti", label: "Log bukti" }, { value: "ekspor", label: "Ekspor & retensi" },
      ]} />
      {tab === "etika" && <Ethics />}
      {tab === "kesimpulan" && <Conclusions />}
      {tab === "bukti" && <EvidenceLog />}
      {tab === "ekspor" && <ExportRetention />}
    </Page>
  );
}

const ETHICS_FIELDS: [string, string, "text" | "area" | "date" | "number"][] = [
  ["name", "Nama proyek", "text"], ["description", "Deskripsi", "area"], ["ethics_body", "Komisi etik", "text"],
  ["ethics_approval_ref", "Nomor persetujuan etik", "text"], ["ethics_approval_date", "Tanggal persetujuan", "date"],
  ["consent_notes", "Persetujuan & dasar pemrosesan", "area"], ["data_minimization_notes", "Minimisasi data", "area"],
  ["risk_mitigation_notes", "Mitigasi risiko", "area"], ["raw_retention_days", "Retensi teks mentah (hari)", "number"],
  ["retention_days", "Retensi data terolah (hari)", "number"],
];

function Ethics() {
  const { can } = useApp();
  const { data, error, setData } = useApi<any>("/api/project");
  const [form, setForm] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (data) setForm(data); }, [data]);
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!form) return <Spinner />;
  const editable = can("manage_project");
  async function save() {
    const body: any = {};
    for (const [k] of ETHICS_FIELDS) if (form[k] !== data[k]) body[k] = form[k];
    const r = await api("/api/project", { method: "PATCH", body: JSON.stringify(body) });
    setData(r);
    setMsg("Dokumentasi etika disimpan dan tercatat di log audit.");
  }
  return (
    <Card>
      <CardHeader title={`${data.code} · periode ${fmtDate(data.period_start)} – ${fmtDate(data.period_end)}`}
        subtitle="Dokumentasi ini menyertai setiap ekspor." right={editable && <Button size="sm" onClick={save}><Save />Simpan</Button>} />
      <div className="grid gap-3 p-4 md:grid-cols-2">
        {ETHICS_FIELDS.map(([k, label, type]) => (
          <label key={k} className={type === "area" ? "md:col-span-2" : ""}>
            <span className="label-xs">{label}</span>
            {type === "area" ? (
              <Textarea rows={2} className="mt-1" value={form[k] ?? ""} disabled={!editable} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            ) : (
              <Input className="mt-1 [color-scheme:dark]" type={type} value={form[k] ?? ""} disabled={!editable}
                onChange={(e) => setForm({ ...form, [k]: type === "number" ? Number(e.target.value) : e.target.value })} />
            )}
          </label>
        ))}
        {msg && <div className="md:col-span-2"><Notice>{msg}</Notice></div>}
      </div>
    </Card>
  );
}

function Conclusions() {
  const { can, user } = useApp();
  const { data, error, reload } = useApi<any[]>("/api/annotations");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState("kesimpulan");
  const [tags, setTags] = useState("");
  const [err, setErr] = useState<string | null>(null);
  async function create() {
    setErr(null);
    try {
      await api("/api/annotations", { method: "POST", body: JSON.stringify({ target_type: "proyek", kind, body, tags: tags.split(",").map((t) => t.trim()).filter(Boolean) }) });
      setBody(""); setTags(""); reload();
    } catch (e) { setErr((e as Error).message); }
  }
  async function review(id: number, decision: string) {
    setErr(null);
    try { await api(`/api/annotations/${id}/review`, { method: "POST", body: JSON.stringify({ decision }) }); reload(); }
    catch (e) { setErr((e as Error).message); }
  }
  const tone: Record<string, string> = { draf: "#94A3B8", perlu_tinjauan: "#FBBF24", disetujui: "#2DD4BF", ditolak: "#F87171" };
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card>
        <CardHeader title="Anotasi & kesimpulan" subtitle="Kesimpulan hanya dapat dipublikasikan/diekspor setelah disetujui peninjau yang BUKAN penulisnya." />
        {error && <div className="p-3"><ErrorBox>{error}</ErrorBox></div>}
        {err && <div className="p-3"><ErrorBox>{err}</ErrorBox></div>}
        <div className="divide-y divide-line">
          {!data && <div className="p-4"><Spinner /></div>}
          {data?.length === 0 && <div className="p-4"><Empty>Belum ada anotasi.</Empty></div>}
          {data?.map((a) => (
            <div key={a.id} className="p-3 text-xs">
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge color="#A78BFA">{a.kind}</Badge>
                <Badge color={tone[a.review_status]}>{a.review_status.replace("_", " ")}</Badge>
                <span className="text-2xs text-dim">{a.target_type}{a.target_id ? ` #${a.target_id}` : ""} · {a.author} · {fmtDateTime(a.created_at)}</span>
                {a.reviewer && <span className="text-2xs text-dim">· ditinjau {a.reviewer}</span>}
                {a.tags.map((t: string) => <span key={t} className="rounded bg-bg/70 px-1 font-mono text-2xs text-mute">#{t}</span>)}
              </div>
              <p className="mt-1.5 leading-relaxed">{a.body}</p>
              {a.kind === "kesimpulan" && a.review_status === "perlu_tinjauan" && can("approve_conclusion") && a.author_id !== user?.id && (
                <div className="mt-2 flex gap-1.5">
                  <Button size="sm" onClick={() => review(a.id, "disetujui")}><Check />Setujui</Button>
                  <Button size="sm" variant="danger" onClick={() => review(a.id, "ditolak")}><X />Tolak</Button>
                </div>
              )}
            </div>
          ))}
        </div>
      </Card>
      {can("annotate") && (
        <Card className="h-fit">
          <CardHeader title="Tulis anotasi" />
          <div className="space-y-2 p-4">
            <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-full">
              <option value="kesimpulan">Kesimpulan (perlu tinjauan kedua)</option><option value="catatan">Catatan</option><option value="kode">Kode kualitatif</option>
            </Select>
            <Textarea rows={5} placeholder="Tulis temuan pada tingkat pola/konten. Hindari menilai atau mengidentifikasi individu." value={body} onChange={(e) => setBody(e.target.value)} />
            <Input placeholder="tag, dipisah koma" value={tags} onChange={(e) => setTags(e.target.value)} />
            <Button onClick={create} disabled={body.trim().length < 3}>Simpan</Button>
          </div>
        </Card>
      )}
    </div>
  );
}

function EvidenceLog() {
  const { data, error } = useApi<any[]>("/api/evidence");
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return <Spinner />;
  return (
    <Card>
      <CardHeader title={`Log bukti (${data.length})`} subtitle="Semua catatan bukti pendukung, bertentangan, dan celah data — sumber utama untuk audit klaim difusi." />
      <div className="max-h-[70vh] overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-panel"><tr className="label-xs text-left"><th className="px-3 py-2">Relasi / konten</th><th>Status relasi</th><th>Jenis bukti</th><th>Arah</th><th>Kekuatan</th><th className="px-3">Deskripsi</th></tr></thead>
          <tbody className="divide-y divide-line/60">
            {data.map((e) => (
              <tr key={e.id}>
                <td className="px-3 py-1.5 font-mono">{e.relationship ? `${e.relationship.source} → ${e.relationship.target}` : e.content}</td>
                <td>{e.relationship && <Badge color={EVIDENCE_COLORS[e.relationship.evidence_status]}>{EVIDENCE_LABELS[e.relationship.evidence_status]}</Badge>}</td>
                <td className="font-mono text-2xs text-mute">{e.evidence_type}</td>
                <td><Badge color={e.direction === "mendukung" ? "#2DD4BF" : e.direction === "bertentangan" ? "#F87171" : "#94A3B8"}>{e.direction}</Badge></td>
                <td className="font-mono text-mute">{e.strength}</td>
                <td className="max-w-xl px-3 text-2xs text-mute">{e.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function ExportRetention() {
  const { can } = useApp();
  const fp = useFilterParams();
  const [layer, setLayer] = useState("aktor");
  const [withText, setWithText] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ret, setRet] = useState<any>(null);
  const exp = (format: string) => download(`/api/export/anonymized${qs({ ...fp, layer, format, include_text: withText })}`, `laras_ekspor.${format}`).catch((e) => setErr(e.message));
  async function retention(dry: boolean) {
    setErr(null);
    try { setRet(await api(`/api/retention/apply?dry_run=${dry}`, { method: "POST" })); } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader title="Ekspor hasil riset anonim" subtitle="Pseudonim + metrik + komunitas + label tervalidasi + kesimpulan yang disetujui. Tanpa handle, URL, atau ID platform." />
        <div className="space-y-3 p-4 text-xs">
          {!can("export") ? <Empty>Peran Anda tidak memiliki izin ekspor.</Empty> : (
            <>
              <div className="flex items-center gap-2"><span className="label-xs">Lapisan jaringan</span>
                <Select value={layer} onChange={(e) => setLayer(e.target.value)}><option value="aktor">Aktor–aktor</option><option value="konten">Difusi konten</option><option value="bipartit">Aktor–konten</option></Select></div>
              <Switch checked={withText} onChange={setWithText} label="Sertakan teks konten (izin export_raw; konten sensitif tetap dikecualikan)" />
              <div className="flex gap-2">
                <Button onClick={() => exp("json")}><Download />JSON lengkap</Button>
                <Button variant="secondary" onClick={() => exp("csv")}><Download />CSV konten</Button>
              </div>
              <Notice>Filter periode, platform, dan kategori di bilah atas ikut diterapkan. Setiap ekspor tercatat di log audit.</Notice>
            </>
          )}
          {err && <ErrorBox>{err}</ErrorBox>}
        </div>
      </Card>
      <Card>
        <CardHeader title="Retensi data mentah" subtitle="Menghapus teks mentah yang melewati masa retensi; data terolah (label, metrik) tetap." />
        <div className="space-y-3 p-4 text-xs">
          {!can("manage_project") ? <Empty>Hanya peneliti utama/admin.</Empty> : (
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => retention(true)}>Simulasikan</Button>
              <Button variant="danger" onClick={() => retention(false)} disabled={!ret || ret.affected === 0}><Trash2 />Terapkan penghapusan</Button>
            </div>
          )}
          {ret && <Notice tone={ret.dry_run ? "info" : "warn"}>{ret.dry_run ? "Simulasi" : "Diterapkan"}: {ret.affected} konten dikumpulkan sebelum {fmtDate(ret.cutoff)}.</Notice>}
        </div>
      </Card>
    </div>
  );
}
