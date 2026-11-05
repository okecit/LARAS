"use client";

import { Info, Loader2 } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/format";

export function Card({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-line bg-panel/80", className)} {...p} />;
}

export function CardHeader({ title, subtitle, right, className }: { title: React.ReactNode; subtitle?: React.ReactNode; right?: React.ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-3 border-b border-line px-4 py-3", className)}>
      <div className="min-w-0">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-2xs text-mute">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Badge({ children, color, className, title }: { children: React.ReactNode; color?: string; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cn("tone inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-2xs font-medium leading-none ring-1 ring-inset", className)}
      style={color ? { color, backgroundColor: `${color}1A`, boxShadow: `inset 0 0 0 1px ${color}40` } : undefined}
    >
      {children}
    </span>
  );
}

export function Dot({ color, size = 8 }: { color: string; size?: number }) {
  return <span className="inline-block shrink-0 rounded-full" style={{ backgroundColor: color, width: size, height: size }} />;
}

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...p }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-8 w-full rounded-md border border-line2 bg-bg/70 px-2.5 text-xs text-ink placeholder:text-dim focus:border-teal/60 focus:outline-none focus:ring-1 focus:ring-teal/40",
      className,
    )}
    {...p}
  />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...p }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "w-full rounded-md border border-line2 bg-bg/70 px-2.5 py-2 text-xs text-ink placeholder:text-dim focus:border-teal/60 focus:outline-none focus:ring-1 focus:ring-teal/40",
      className,
    )}
    {...p}
  />
));
Textarea.displayName = "Textarea";

export function Select({ className, children, ...p }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn("h-8 rounded-md border border-line2 bg-bg/70 px-2 text-xs text-ink focus:border-teal/60 focus:outline-none", className)}
      {...p}
    >
      {children}
    </select>
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-xs text-mute select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cn("relative h-4 w-7 rounded-full transition-colors", checked ? "bg-teal" : "bg-line2")}
      >
        <span className={cn("absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all", checked ? "left-3.5" : "left-0.5")} />
      </button>
      {label}
    </label>
  );
}

export function Tabs<T extends string>({ value, onChange, items, className }: { value: T; onChange: (v: T) => void; items: { value: T; label: React.ReactNode }[]; className?: string }) {
  return (
    <div className={cn("inline-flex rounded-md border border-line bg-bg/60 p-0.5", className)}>
      {items.map((it) => (
        <button
          key={it.value}
          onClick={() => onChange(it.value)}
          className={cn(
            "rounded px-2.5 py-1 text-2xs font-medium transition-colors",
            value === it.value ? "bg-panel2 text-teal shadow-glow" : "text-mute hover:text-ink",
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

export function Stat({ label, value, hint, accent }: { label: string; value: React.ReactNode; hint?: string; accent?: string }) {
  return (
    <div className="min-w-0">
      <div className="label-xs truncate" title={hint}>{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold tabular-nums" style={accent ? { color: accent } : undefined}>{value}</div>
    </div>
  );
}

export function Spinner({ label = "Memuat…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-mute">
      <Loader2 className="h-4 w-4 animate-spin text-teal" />
      {label}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md border border-dashed border-line2 px-4 py-6 text-center text-xs text-dim">{children}</div>;
}

export function ErrorBox({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">{children}</div>;
}

export function Hint({ text }: { text: string }) {
  return (
    <span className="group relative inline-flex cursor-help align-middle">
      <Info className="h-3 w-3 text-dim group-hover:text-teal" />
      <span className="pointer-events-none absolute left-1/2 top-5 z-50 hidden w-64 -translate-x-1/2 rounded-md border border-line2 bg-panel p-2 text-2xs font-normal normal-case leading-relaxed tracking-normal text-mute shadow-xl group-hover:block">
        {text}
      </span>
    </span>
  );
}

export function Notice({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "warn" }) {
  return (
    <div className={cn("flex gap-2 rounded-md border px-3 py-2 text-2xs leading-relaxed",
      tone === "warn" ? "border-amber/30 bg-amber/5 text-amber/90" : "border-cyan/20 bg-cyan/5 text-mute")}>
      <Info className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", tone === "warn" ? "text-amber" : "text-cyan")} />
      <div>{children}</div>
    </div>
  );
}

export function PageHeader({ title, subtitle, right }: { title: string; subtitle?: string; right?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-0.5 max-w-3xl text-xs text-mute">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}

export function Bar({ value, max, color = "#2DD4BF" }: { value: number; max: number; color?: string }) {
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
      <div className="h-full rounded-full" style={{ width: `${max ? Math.max(2, (value / max) * 100) : 0}%`, backgroundColor: color }} />
    </div>
  );
}
