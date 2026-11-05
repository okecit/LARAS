"use client";

import { LockKeyhole, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Logo } from "@/components/layout/Logo";
import { Button } from "@/components/ui/button";
import { Badge, ErrorBox, Input } from "@/components/ui/primitives";
import { api, setToken } from "@/lib/api";
import { ThemeToggle } from "@/lib/theme";

type DemoAccount = { username: string; role: string; role_label: string };

export default function LoginPage() {
  const [username, setUsername] = useState("ketua");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState<DemoAccount[]>([]);

  useEffect(() => {
    fetch("/api/auth/demo-accounts").then((r) => (r.ok ? r.json() : [])).then(setDemo).catch(() => setDemo([]));
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ access_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
      setToken(res.access_token);
      window.location.href = "/";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid-bg relative flex min-h-screen items-center justify-center p-4">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[3px] bg-brand" />
      <ThemeToggle className="absolute right-4 top-4" />
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <Logo height={96} className="rounded-xl px-3" />
        </div>
        <div className="rounded-xl border border-line bg-panel/90 p-6 shadow-2xl">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <h1 className="text-base font-semibold">Masuk ke ruang kerja riset</h1>
              <p className="text-2xs text-mute">YOUTH-SNA · Youth Social Behavior Network Analytics</p>
            </div>
            <LockKeyhole className="h-5 w-5 text-teal" />
          </div>
          <form onSubmit={submit} className="space-y-3">
            <label className="block">
              <span className="label-xs">Nama pengguna</span>
              <Input className="mt-1" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </label>
            <label className="block">
              <span className="label-xs">Kata sandi</span>
              <Input className="mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </label>
            {error && <ErrorBox>{error}</ErrorBox>}
            <Button type="submit" className="w-full" size="lg" disabled={busy || !username || !password}>
              {busy ? "Memeriksa…" : "Masuk"}
            </Button>
          </form>
          {demo.length > 0 && (
            <div className="mt-5 border-t border-line pt-4">
              <div className="label-xs mb-2">Akun demo (data sintetis) — kata sandi ada di README</div>
              <div className="flex flex-wrap gap-1.5">
                {demo.map((d) => (
                  <button key={d.username} type="button" onClick={() => setUsername(d.username)}
                    className={`rounded-md border px-2 py-1 text-2xs transition-colors ${username === d.username ? "border-teal text-teal" : "border-line2 text-mute hover:text-ink"}`}>
                    {d.username} · {d.role_label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="mt-4 flex items-start gap-2 text-2xs leading-relaxed text-dim">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal" />
          <p>
            Platform riset, bukan alat pengawasan. Aktor dipseudonimkan, label melekat pada konten—bukan pada individu—dan
            setiap akses tercatat di log audit. <Badge color="#FBBF24" className="ml-1">DEMO</Badge>
          </p>
        </div>
      </div>
    </main>
  );
}
