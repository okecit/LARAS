"use client";

import { CheckCircle2, CircleDashed, Download, FileUp, Play, ShieldAlert, ShieldCheck, XCircle } from "lucide-react";
import { useState } from "react";
import { Page } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty, ErrorBox, Input, Notice, PageHeader, Select, Spinner, Switch, Textarea } from "@/components/ui/primitives";
import { api, download } from "@/lib/api";
import { fmtDateTime, PLATFORM_COLORS, PLATFORM_NAMES } from "@/lib/format";
import { useApi, useApp } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
const AUTH_TONE: Record<string, { c: string; l: string }> = {
  terotorisasi: { c: "#2DD4BF", l: "Terotorisasi" }, terkonfigurasi: { c: "#60A5FA", l: "Terkonfigurasi" },
  belum_dikonfigurasi: { c: "#94A3B8", l: "Belum dikonfigurasi" }, memerlukan_persetujuan: { c: "#FBBF24", l: "Memerlukan persetujuan" },
  tidak_tersedia: { c: "#F472B6", l: "Placeholder — impor resmi" }, ditolak: { c: "#F87171", l: "Ditolak" },
  demo: { c: "#FBBF24", l: "Demo" }, belum_diperiksa: { c: "#94A3B8", l: "Belum diperiksa" },
};
const JOB_TONE: Record<string, string> = { selesai: "#2DD4BF", gagal: "#F87171", berjalan: "#60A5FA", antri: "#FBBF24", dibatalkan: "#94A3B8" };

export default function DataCollection() {
  const connectors = useApi<any[]>("/api/connectors");
  const sources = useApi<any[]>("/api/sources");
  const jobs = useApi<any[]>("/api/jobs");
  return (
    <Page>
      <PageHeader title="Pengumpulan Data" subtitle="Konektor resmi modular, pelacakan job, dan impor CSV/JSON tervalidasi. Tidak ada pembobolan autentikasi, akun privat, atau klaim izin yang tidak dimiliki." />
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title="Konektor" subtitle="Kredensial dibaca dari variabel lingkungan server — tidak pernah disimpan di basis data." />
          <div className="divide-y divide-line">
            {connectors.loading && <div className="p-4"><Spinner /></div>}
            {connectors.data?.map((c) => {
              const t = AUTH_TONE[c.authorization.status] || AUTH_TONE.belum_diperiksa;
              return (
                <div key={c.key} className="p-3 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{c.label}</span>
                    <Badge color={PLATFORM_COLORS[c.platform]}>{PLATFORM_NAMES[c.platform]}</Badge>
                    <Badge color={t.c} className="ml-auto">{t.l}</Badge>
                  </div>
                  <p className="mt-1 text-2xs leading-relaxed text-mute">{c.notes}</p>
                  <p className="mt-0.5 text-2xs text-dim">{c.authorization.message}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {c.credential_envs.map((e: string) => <code key={e} className="rounded bg-bg/70 px-1 text-2xs text-cyan">{e}</code>)}
                    {c.docs_url && <a href={c.docs_url} target="_blank" rel="noreferrer" className="text-2xs text-teal hover:underline">dokumentasi resmi ↗</a>}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
        <ImportPanel sources={sources.data || []} onDone={() => { jobs.reload(); }} />
      </div>
      <SourcesTable sources={sources.data} reload={sources.reload} />
      <JobsPanel jobs={jobs.data} sources={sources.data || []} reload={jobs.reload} />
    </Page>
  );
}

function SourcesTable({ sources, reload }: { sources: any[] | null; reload: () => void }) {
  const { can } = useApp();
  const [msg, setMsg] = useState<string | null>(null);
  const [edit, setEdit] = useState<{ id: number; legal: string } | null>(null);
  async function check(id: number) {
    const r = await api<any>(`/api/sources/${id}/check`, { method: "POST" });
    setMsg(r.message || "Diperiksa.");
    reload();
  }
  async function saveLegal() {
    if (!edit) return;
    await api(`/api/sources/${edit.id}`, { method: "PATCH", body: JSON.stringify({ legal_basis: edit.legal }) });
    setEdit(null);
    reload();
  }
  return (
    <Card className="mt-4">
      <CardHeader title="Sumber data proyek" subtitle="Setiap sumber wajib mencatat dasar hukum/ToS. Job API ditolak bila dasar hukum belum diisi." />
      {msg && <div className="px-4 pt-3"><Notice>{msg}</Notice></div>}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="label-xs text-left"><th className="px-3 py-2">Sumber</th><th>Platform</th><th>Jenis</th><th>Akses</th><th>Otorisasi</th><th>Kuota harian</th><th className="px-3">Dasar hukum</th><th /></tr></thead>
          <tbody className="divide-y divide-line/60">
            {sources?.map((s) => {
              const t = AUTH_TONE[s.authorization_status] || AUTH_TONE.belum_diperiksa;
              return (
                <tr key={s.id}>
                  <td className="px-3 py-2 font-medium">{s.name}</td>
                  <td>{PLATFORM_NAMES[s.platform]}</td>
                  <td className="text-mute">{s.source_type}</td>
                  <td className="text-mute">{s.access_level}</td>
                  <td><Badge color={t.c}>{t.l}</Badge></td>
                  <td className="font-mono text-mute">{s.quota_daily ? `${s.quota_used_today}/${s.quota_daily}` : "—"}</td>
                  <td className="max-w-xs px-3">
                    {edit?.id === s.id ? (
                      <div className="flex gap-1"><Input value={edit?.legal ?? ""} onChange={(e) => setEdit({ id: s.id, legal: e.target.value })} className="h-7" />
                        <Button size="sm" onClick={saveLegal}>Simpan</Button></div>
                    ) : (
                      <span className={`line-clamp-2 text-2xs ${s.legal_basis.includes("Wajib diisi") ? "text-amber" : "text-mute"}`}>{s.legal_basis}</span>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3">
                    {can("manage_sources") && s.source_type !== "demo" && (
                      <div className="flex gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setEdit({ id: s.id, legal: s.legal_basis })}>Ubah</Button>
                        <Button size="sm" variant="secondary" onClick={() => check(s.id)}><ShieldCheck />Cek</Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function JobsPanel({ jobs, sources, reload }: { jobs: any[] | null; sources: any[]; reload: () => void }) {
  const { can } = useApp();
  const apiSources = sources.filter((s) => s.source_type === "api" && s.connector_key !== "meta_content_library");
  const [sid, setSid] = useState<string>("");
  const [query, setQuery] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  async function create() {
    setErr(null);
    try {
      await api("/api/jobs", { method: "POST", body: JSON.stringify({ source_id: Number(sid), query, params: { max_results: 25 } }) });
      setQuery("");
      setTimeout(reload, 1200);
      reload();
    } catch (e) { setErr((e as Error).message); }
  }
  return (
    <Card className="mt-4">
      <CardHeader title="Job pengumpulan" subtitle="Status, kuota terpakai, duplikat, dan log galat per job. Job dijalankan worker latar." right={<Button size="sm" variant="ghost" onClick={reload}>Muat ulang</Button>} />
      {can("run_jobs") && (
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <Select value={sid} onChange={(e) => setSid(e.target.value)}>
            <option value="">Pilih sumber API…</option>
            {apiSources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
          <Input placeholder="Kueri (mis. kata kunci kategori)" value={query} onChange={(e) => setQuery(e.target.value)} className="w-72" />
          <Button size="sm" onClick={create} disabled={!sid || query.length < 2}><Play />Jalankan job</Button>
          {err && <ErrorBox>{err}</ErrorBox>}
        </div>
      )}
      <div className="divide-y divide-line/60">
        {!jobs && <div className="p-4"><Spinner /></div>}
        {jobs?.length === 0 && <div className="p-4"><Empty>Belum ada job.</Empty></div>}
        {jobs?.map((j) => (
          <div key={j.id} className="px-3 py-2 text-xs">
            <button className="flex w-full items-center gap-3 text-left" onClick={() => setOpen(open === j.id ? null : j.id)}>
              {j.status === "selesai" ? <CheckCircle2 className="h-4 w-4 text-teal" /> : j.status === "gagal" ? <XCircle className="h-4 w-4 text-danger" /> : <CircleDashed className="h-4 w-4 animate-spin text-amber" />}
              <span className="font-mono text-dim">#{j.id}</span>
              <span className="font-medium">{j.source}</span>
              <span className="truncate text-mute">{j.query}</span>
              <span className="ml-auto flex items-center gap-3 font-mono text-2xs text-mute">
                <span>baru {j.items_new}</span><span>duplikat {j.items_duplicate}</span><span>ditolak {j.items_rejected}</span><span>kuota {j.quota_used}</span>
                <Badge color={JOB_TONE[j.status]}>{j.status}</Badge>
                <span>{fmtDateTime(j.created_at)}</span>
              </span>
            </button>
            {open === j.id && (
              <pre className="mt-2 max-h-48 overflow-auto rounded bg-bg/70 p-2 text-2xs text-mute">{j.error_log.length ? JSON.stringify(j.error_log, null, 1) : "Tidak ada log galat."}</pre>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function ImportPanel({ sources, onDone }: { sources: any[]; onDone: () => void }) {
  const { can } = useApp();
  const importSources = sources.filter((s) => s.source_type !== "demo");
  const [file, setFile] = useState<File | null>(null);
  const [sid, setSid] = useState("");
  const [legal, setLegal] = useState("");
  const [platform, setPlatform] = useState("");
  const [dry, setDry] = useState(true);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!file) return;
    setBusy(true);
    setErr(null);
    const fd = new FormData();
    fd.append("file", file);
    fd.append("source_id", sid);
    fd.append("legal_basis", legal);
    fd.append("dry_run", String(dry));
    if (platform) fd.append("default_platform", platform);
    try {
      setRes(await api("/api/import", { method: "POST", body: fd }));
      if (!dry) onDone();
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  if (!can("import")) return <Card><CardHeader title="Impor CSV/JSON" /><div className="p-4"><Empty>Peran Anda tidak memiliki izin impor.</Empty></div></Card>;
  return (
    <Card>
      <CardHeader title="Impor CSV/JSON (alur data sah)" subtitle="Validasi skema → normalisasi waktu ke UTC → pseudonimisasi → deduplikasi → klasifikasi."
        right={<Button size="sm" variant="secondary" onClick={() => download("/api/import/template", "templat_impor_laras.csv")}><Download />Templat CSV</Button>} />
      <div className="space-y-2.5 p-4 text-xs">
        <label className="flex cursor-pointer items-center gap-3 rounded-md border border-dashed border-line2 p-3 hover:border-teal/50">
          <FileUp className="h-5 w-5 text-teal" />
          <span className="text-mute">{file ? `${file.name} (${(file.size / 1024).toFixed(1)} KB)` : "Pilih berkas .csv atau .json (maks. 5 MB)"}</span>
          <input type="file" accept=".csv,.json" className="hidden" onChange={(e) => { setFile(e.target.files?.[0] || null); setRes(null); }} />
        </label>
        <div className="grid grid-cols-2 gap-2">
          <Select value={sid} onChange={(e) => setSid(e.target.value)}>
            <option value="">Sumber data…</option>
            {importSources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
          <Select value={platform} onChange={(e) => setPlatform(e.target.value)}>
            <option value="">Platform dari kolom berkas</option>
            {["tiktok", "instagram", "youtube", "x", "lainnya"].map((p) => <option key={p} value={p}>Bawaan: {PLATFORM_NAMES[p]}</option>)}
          </Select>
        </div>
        <Textarea rows={2} placeholder="Dasar hukum / izin akses (mis. ekspor Meta Content Library proyek #…, sesuai ketentuan) — wajib" value={legal} onChange={(e) => setLegal(e.target.value)} />
        <div className="flex items-center justify-between">
          <Switch checked={dry} onChange={setDry} label="Uji coba (validasi saja, tanpa menyimpan)" />
          <Button onClick={submit} disabled={!file || !sid || legal.length < 10 || busy}>{dry ? "Validasi" : "Impor & simpan"}</Button>
        </div>
        {err && <ErrorBox>{err}</ErrorBox>}
        {res && (
          <div className="space-y-2 rounded-md border border-line bg-bg/40 p-3">
            <div className="flex flex-wrap gap-2 font-mono text-2xs">
              <Badge color="#94A3B8">baris {res.validation.total_rows}</Badge><Badge color="#2DD4BF">valid {res.validation.valid_rows}</Badge>
              <Badge color="#F87171">tidak valid {res.validation.invalid_rows}</Badge><Badge color="#FBBF24">duplikat dlm berkas {res.validation.duplicates_in_file}</Badge>
              {res.result && <Badge color="#22D3EE">tersimpan {res.result.new} · duplikat DB {res.result.duplicate} · relasi {res.result.relations}</Badge>}
            </div>
            {res.validation.errors.length > 0 && (
              <div className="max-h-40 overflow-auto">
                {res.validation.errors.map((e: any, i: number) => (
                  <div key={i} className="flex gap-2 text-2xs"><ShieldAlert className="h-3 w-3 text-danger" /><span className="font-mono">baris {e.row}</span><span className="text-amber">{e.field}</span><span className="text-mute">{e.message}</span></div>
                ))}
              </div>
            )}
            {dry && res.validation.valid_rows > 0 && <p className="text-2xs text-teal">Validasi lolos. Matikan “Uji coba” untuk menyimpan.</p>}
          </div>
        )}
      </div>
    </Card>
  );
}
