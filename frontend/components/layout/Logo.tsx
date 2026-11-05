/* eslint-disable @next/next/no-img-element */
import { cn } from "@/lib/format";

/** Logo LARAs. Logo asli berlatar putih, jadi ditempatkan pada lencana terang agar kontras di tema gelap. */
export function Logo({ className, height = 40 }: { className?: string; height?: number }) {
  return (
    <div
      className={cn("flex shrink-0 items-center rounded-md bg-white px-1.5 ring-1 ring-line shadow-[0_0_24px_-10px_rgba(30,200,230,.55)]", className)}
      style={{ height: height + 6 }}
    >
      <img src="/brand/laras-logo.jpeg" alt="LARAs — Lacak Aktivitas Remaja di Ruang Siber" style={{ height }} className="w-auto max-w-none select-none" draggable={false} />
    </div>
  );
}
