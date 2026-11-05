"use client";

import {
  Boxes, CalendarRange, ChevronDown, Database, GitBranch, LayoutDashboard, LogOut, NotebookPen, ScanText, Search, Settings, Share2, Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Badge, Dot, ErrorBox, Input, Spinner } from "@/components/ui/primitives";
import { cn, PLATFORM_COLORS, PLATFORM_NAMES } from "@/lib/format";
import { AppProvider, useApp } from "@/lib/store";
import { Logo } from "./Logo";

const NAV = [
  { href: "/", label: "Network Explorer", icon: Share2 },
  { href: "/overview", label: "Ikhtisar", icon: LayoutDashboard },
  { href: "/content", label: "Content Intelligence", icon: ScanText },
  { href: "/diffusion", label: "Diffusion Tracker", icon: GitBranch },
  { href: "/actors", label: "Actor Analytics", icon: Users },
  { href: "/communities", label: "Deteksi Komunitas", icon: Boxes },
  { href: "/collection", label: "Pengumpulan Data", icon: Database },
  { href: "/workspace", label: "Ruang Kerja Riset", icon: NotebookPen },
  { href: "/settings", label: "Pengaturan", icon: Settings },
];

export function Shell({ children }: { children: ReactNode }) {
  return (
    <AppProvider>
      <ShellInner>{children}</ShellInner>
    </AppProvider>
  );
}

function ShellInner({ children }: { children: ReactNode }) {
  const { loading, error, user } = useApp();
  const path = usePathname();
  if (loading) return <div className="grid-bg flex h-screen items-center justify-center"><Spinner label="Menyiapkan ruang kerja…" /></div>;
  if (error || !user) return <div className="flex h-screen items-center justify-center p-6"><ErrorBox>{error || "Sesi tidak valid."}</ErrorBox></div>;
  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <nav className="flex w-[212px] shrink-0 flex-col border-r border-line bg-panel/70">
          <div className="flex-1 space-y-0.5 overflow-y-auto p-2">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = href === "/" ? path === "/" : path.startsWith(href);
              return (
                <Link key={href} href={href}
                  className={cn("flex items-center gap-2.5 rounded-md px-2.5 py-2 text-xs transition-colors",
                    active ? "bg-teal/10 text-teal ring-1 ring-inset ring-teal/30" : "text-mute hover:bg-panel2 hover:text-ink")}>
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </div>
          <UserBox />
        </nav>
        <main className="min-w-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}

function UserBox() {
  const { user, logout } = useApp();
  if (!user) return null;
  return (
    <div className="border-t border-line p-3">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-teal to-purple text-2xs font-bold text-bg">
          {user.display_name.slice(0, 1)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-xs font-medium">{user.display_name}</div>
          <div className="truncate text-2xs text-dim">{user.role_label}</div>
        </div>
        <button onClick={logout} title="Keluar" className="text-dim hover:text-danger"><LogOut className="h-4 w-4" /></button>
      </div>
    </div>
  );
}

function TopBar() {
  const { meta, filters, setFilters } = useApp();
  if (!meta) return null;
  const togglePlatform = (p: string) =>
    setFilters({ platforms: filters.platforms.includes(p) ? filters.platforms.filter((x) => x !== p) : [...filters.platforms, p] });
  return (
    <header className="flex h-[60px] shrink-0 items-center gap-3 border-b border-line bg-panel/90 px-3 backdrop-blur">
      <Link href="/" title="LARAs — beranda"><Logo height={40} /></Link>
      <div className="hidden min-w-0 flex-col xl:flex">
        <span className="truncate text-xs font-semibold text-ink" title={meta.project.name}>{meta.project.name}</span>
        <span className="font-mono text-2xs text-dim">{meta.project.code} · YOUTH-SNA</span>
      </div>
      <div className="mx-1 h-8 w-px bg-line" />
      <div className="flex items-center gap-1.5" title="Periode riset">
        <CalendarRange className="h-4 w-4 text-dim" />
        <input type="date" value={filters.start} min={meta.project.period_start} max={filters.end}
          onChange={(e) => setFilters({ start: e.target.value })}
          className="h-7 rounded border border-line2 bg-bg/70 px-1.5 font-mono text-2xs text-ink [color-scheme:dark]" />
        <span className="text-dim">–</span>
        <input type="date" value={filters.end} min={filters.start} max={meta.project.period_end}
          onChange={(e) => setFilters({ end: e.target.value })}
          className="h-7 rounded border border-line2 bg-bg/70 px-1.5 font-mono text-2xs text-ink [color-scheme:dark]" />
      </div>
      <div className="flex items-center gap-1" role="group" aria-label="Filter platform">
        {meta.platforms.filter((p) => p.code !== "lainnya").map((p) => {
          const on = filters.platforms.length === 0 || filters.platforms.includes(p.code);
          return (
            <button key={p.code} onClick={() => togglePlatform(p.code)}
              className={cn("flex h-7 items-center gap-1.5 rounded-md border px-2 text-2xs transition-colors",
                filters.platforms.includes(p.code) ? "border-teal/60 bg-teal/10 text-ink" : "border-line2 text-mute hover:text-ink",
                !on && "opacity-40")}>
              <Dot color={PLATFORM_COLORS[p.code]} size={7} />
              {PLATFORM_NAMES[p.code]}
            </button>
          );
        })}
      </div>
      <CategoryPicker />
      <div className="relative ml-auto w-56">
        <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-dim" />
        <Input placeholder="Cari pseudonim / kode konten…" className="pl-8" value={filters.search}
          onChange={(e) => setFilters({ search: e.target.value })} />
      </div>
      <Badge color={meta.data_mode === "DEMO" ? "#FBBF24" : "#2DD4BF"} className="h-7 px-2 text-xs"
        title={meta.data_mode === "DEMO" ? "Data sintetis — akun & konten fiktif" : "Data hasil pengumpulan resmi"}>
        <span className={cn("h-1.5 w-1.5 rounded-full", meta.data_mode === "DEMO" ? "bg-amber" : "animate-pulse bg-teal")} />
        {meta.data_mode}
      </Badge>
    </header>
  );
}

function CategoryPicker() {
  const { meta, filters, setFilters } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  if (!meta) return null;
  const sel = filters.categories;
  const toggle = (c: string) => setFilters({ categories: sel.includes(c) ? sel.filter((x) => x !== c) : [...sel, c] });
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(!open)}
        className={cn("flex h-7 items-center gap-1.5 rounded-md border px-2 text-2xs", sel.length ? "border-purple/60 text-ink" : "border-line2 text-mute")}>
        Kategori
        {sel.length > 0 ? (
          <span className="flex gap-0.5">{sel.map((c) => <Dot key={c} color={meta.categories.find((x) => x.code === c)?.color || "#fff"} size={7} />)}</span>
        ) : <span className="text-dim">semua</span>}
        <ChevronDown className="h-3 w-3" />
      </button>
      {open && (
        <div className="absolute left-0 top-9 z-50 w-80 rounded-lg border border-line2 bg-panel p-2 shadow-2xl">
          {meta.categories.map((c) => (
            <label key={c.code} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs hover:bg-panel2">
              <input type="checkbox" checked={sel.includes(c.code)} onChange={() => toggle(c.code)} />
              <Dot color={c.color} />
              <span className="font-mono text-2xs text-dim">{c.code}</span>
              <span className="truncate">{c.name}</span>
            </label>
          ))}
          <div className="mt-1 flex justify-between border-t border-line px-2 pt-2">
            <button className="text-2xs text-mute hover:text-teal" onClick={() => setFilters({ categories: [] })}>Hapus pilihan</button>
            <button className="text-2xs text-teal" onClick={() => setOpen(false)}>Selesai</button>
          </div>
        </div>
      )}
    </div>
  );
}
