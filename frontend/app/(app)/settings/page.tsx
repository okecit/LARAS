"use client";

import { Check, Minus, UserPlus } from "lucide-react";
import { useState } from "react";
import { Page } from "@/components/layout/Page";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardHeader, Empty, ErrorBox, Input, PageHeader, Select, Spinner, Tabs } from "@/components/ui/primitives";
import { api } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { useApi, useApp } from "@/lib/store";

/* eslint-disable @typescript-eslint/no-explicit-any */
const ROLES = ["admin", "peneliti_utama", "peneliti", "peninjau", "pengamat"];
const ROLE_LABELS: Record<string, string> = { admin: "Admin", peneliti_utama: "Peneliti Utama", peneliti: "Peneliti", peninjau: "Peninjau", pengamat: "Pengamat" };
const PERMS: [string, string, string[]][] = [
  ["view", "Melihat dasbor & graf", ["admin", "peneliti_utama", "peneliti", "peninjau", "pengamat"]],
  ["view_raw", "Melihat teks mentah", ["admin", "peneliti_utama", "peneliti", "peninjau"]],
  ["annotate", "Menulis anotasi", ["admin", "peneliti_utama", "peneliti", "peninjau"]],
  ["validate", "Validasi label & status bukti", ["admin", "peneliti_utama", "peninjau"]],
  ["approve_conclusion", "Menyetujui kesimpulan", ["admin", "peneliti_utama", "peninjau"]],
  ["edit_evidence", "Mencatat bukti difusi", ["admin", "peneliti_utama", "peneliti", "peninjau"]],
  ["edit_taxonomy", "Mengubah taksonomi", ["admin", "peneliti_utama"]],
  ["import", "Impor berkas", ["admin", "peneliti_utama", "peneliti"]],
  ["run_jobs", "Menjalankan job API", ["admin", "peneliti_utama", "peneliti"]],
  ["manage_sources", "Mengelola sumber & kredensial", ["admin", "peneliti_utama"]],
  ["export", "Ekspor anonim", ["admin", "peneliti_utama", "peneliti"]],
  ["export_raw", "Ekspor dengan teks", ["admin", "peneliti_utama"]],
  ["manage_project", "Etika, retensi, proyek", ["admin", "peneliti_utama"]],
  ["view_audit", "Melihat log audit", ["admin", "peneliti_utama"]],
  ["manage_users", "Mengelola pengguna", ["admin"]],
];

export default function SettingsPage() {
  const { can } = useApp();
  const [tab, setTab] = useState<"peran" | "pengguna" | "audit" | "metrik">("peran");
  return (
    <Page>
      <PageHeader title="Pengaturan" subtitle="Kontrol akses berbasis peran, pengguna, log audit, dan penjelasan metrik." />
      <Tabs className="mb-4" value={tab} onChange={setTab} items={[
        { value: "peran", label: "Peran & izin" }, { value: "pengguna", label: "Pengguna" }, { value: "audit", label: "Log audit" }, { value: "metrik", label: "Penjelasan metrik" },
      ]} />
      {tab === "peran" && <RoleMatrix />}
      {tab === "pengguna" && (can("manage_users") ? <Users /> : <Empty>Hanya administrator.</Empty>)}
      {tab === "audit" && (can("view_audit") ? <Audit /> : <Empty>Peran Anda tidak memiliki akses log audit.</Empty>)}
      {tab === "metrik" && <MetricDocs />}
    </Page>
  );
}

function RoleMatrix() {
  return (
    <Card>
      <CardHeader title="Matriks izin RBAC" subtitle="Izin ditegakkan di server pada setiap endpoint API." />
      <table className="w-full text-xs">
        <thead><tr className="label-xs"><th className="px-4 py-2 text-left">Izin</th>{ROLES.map((r) => <th key={r} className="px-2">{ROLE_LABELS[r]}</th>)}</tr></thead>
        <tbody className="divide-y divide-line/60">
          {PERMS.map(([k, label, roles]) => (
            <tr key={k}><td className="px-4 py-1.5">{label} <span className="font-mono text-2xs text-dim">{k}</span></td>
              {ROLES.map((r) => <td key={r} className="text-center">{roles.includes(r) ? <Check className="mx-auto h-3.5 w-3.5 text-teal" /> : <Minus className="mx-auto h-3.5 w-3.5 text-line2" />}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function Users() {
  const { data, error, reload } = useApi<any[]>("/api/users");
  const [form, setForm] = useState({ username: "", display_name: "", role: "peneliti", password: "" });
  const [err, setErr] = useState<string | null>(null);
  async function create() {
    setErr(null);
    try { await api("/api/users", { method: "POST", body: JSON.stringify(form) }); setForm({ username: "", display_name: "", role: "peneliti", password: "" }); reload(); }
    catch (e) { setErr((e as Error).message); }
  }
  async function patch(id: number, body: any) {
    setErr(null);
    try { await api(`/api/users/${id}`, { method: "PATCH", body: JSON.stringify(body) }); reload(); } catch (e) { setErr((e as Error).message); }
  }
  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Card>
        <CardHeader title="Pengguna riset" />
        {error && <ErrorBox>{error}</ErrorBox>}
        {!data ? <div className="p-4"><Spinner /></div> : (
          <table className="w-full text-xs">
            <thead><tr className="label-xs text-left"><th className="px-4 py-2">Pengguna</th><th>Peran</th><th>Status</th><th>Login terakhir</th></tr></thead>
            <tbody className="divide-y divide-line/60">
              {data.map((u) => (
                <tr key={u.id}>
                  <td className="px-4 py-1.5"><div className="font-medium">{u.display_name}</div><div className="font-mono text-2xs text-dim">{u.username}</div></td>
                  <td><Select value={u.role} onChange={(e) => patch(u.id, { role: e.target.value })}>{ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</Select></td>
                  <td><button onClick={() => patch(u.id, { is_active: !u.is_active })}><Badge color={u.is_active ? "#2DD4BF" : "#F87171"}>{u.is_active ? "aktif" : "nonaktif"}</Badge></button></td>
                  <td className="text-mute">{fmtDateTime(u.last_login_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <Card className="h-fit">
        <CardHeader title="Tambah pengguna" />
        <div className="space-y-2 p-4">
          <Input placeholder="nama pengguna" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} />
          <Input placeholder="nama tampilan" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} className="w-full">{ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}</Select>
          <Input type="password" placeholder="kata sandi (min. 10 karakter)" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <Button onClick={create} disabled={!form.username || !form.display_name || form.password.length < 10}><UserPlus />Tambah</Button>
          {err && <ErrorBox>{err}</ErrorBox>}
        </div>
      </Card>
    </div>
  );
}

function Audit() {
  const { data, error } = useApi<any[]>("/api/audit?limit=300");
  if (error) return <ErrorBox>{error}</ErrorBox>;
  if (!data) return <Spinner />;
  return (
    <Card>
      <CardHeader title="Log audit" subtitle="Login, ekspor, perubahan taksonomi, validasi, bukti, impor, dan retensi." />
      <div className="max-h-[70vh] overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-panel"><tr className="label-xs text-left"><th className="px-4 py-2">Waktu</th><th>Pengguna</th><th>Aksi</th><th>Sumber daya</th><th className="px-4">Rincian</th></tr></thead>
          <tbody className="divide-y divide-line/60">
            {data.map((a) => (
              <tr key={a.id}>
                <td className="whitespace-nowrap px-4 py-1.5 text-mute">{fmtDateTime(a.created_at)}</td>
                <td className="font-mono">{a.username}</td>
                <td><Badge color={a.action.includes("gagal") ? "#F87171" : a.action.startsWith("ekspor") ? "#FBBF24" : "#60A5FA"}>{a.action}</Badge></td>
                <td className="font-mono text-2xs text-mute">{a.resource_type}{a.resource_id ? `#${a.resource_id}` : ""}</td>
                <td className="max-w-lg truncate px-4 font-mono text-2xs text-dim">{JSON.stringify(a.details)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function MetricDocs() {
  const { meta } = useApp();
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {Object.entries(meta?.metrics || {}).map(([k, m]) => (
        <Card key={k} className="p-4">
          <div className="flex items-center gap-2"><span className="text-sm font-semibold">{m.label}</span><span className="font-mono text-2xs text-dim">{k}</span></div>
          <p className="mt-1.5 text-xs leading-relaxed text-mute">{m.explanation}</p>
        </Card>
      ))}
      <Card className="border-amber/30 p-4 md:col-span-2"><p className="text-xs leading-relaxed text-amber/90">{meta?.disclaimer}</p></Card>
    </div>
  );
}
