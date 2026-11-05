/* eslint-disable @next/next/no-img-element */
import { cn } from "@/lib/format";

/** Logo LARAs. Logo asli berlatar putih, jadi ditempatkan pada lencana terang agar kontras di tema gelap. */
export function Logo({ className, height = 40 }: { className?: string; height?: number }) {
  return (
    <div
      className={cn("flex shrink-0 items-center rounded-md bg-white px-1.5 ring-1 ring-white/10 shadow-[0_0_24px_-8px_rgba(34,211,238,.6)]", className)}
      style={{ height: height + 6 }}
    >
      <img src="/brand/laras-logo.jpeg" alt="LARAs — Lacak Aktivitas Remaja di Ruang Siber" style={{ height }} className="w-auto select-none" draggable={false} />
    </div>
  );
}
