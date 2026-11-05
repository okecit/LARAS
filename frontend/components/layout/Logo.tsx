"use client";
/* eslint-disable @next/next/no-img-element */
import { cn } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const ALT = "LARAs — Lacak Aktivitas Remaja di Ruang Siber";

/** Logo LARAs sesuai tema: versi latar gelap untuk tema gelap, versi latar putih untuk tema terang. */
export function Logo({ className, height = 40 }: { className?: string; height?: number }) {
  const { theme } = useTheme();
  if (theme === "dark") {
    return (
      <div className={cn("flex shrink-0 items-center overflow-hidden rounded-md ring-1 ring-line2/70 shadow-[0_0_24px_-10px_rgba(30,200,230,.6)]", className)}
        style={{ height: height + 6 }}>
        <img src="/brand/laras-logo-dark.webp" alt={ALT} style={{ height: height + 6 }} className="w-auto max-w-none select-none" draggable={false} />
      </div>
    );
  }
  return (
    <div className={cn("flex shrink-0 items-center rounded-md bg-white px-1.5 ring-1 ring-line", className)} style={{ height: height + 6 }}>
      <img src="/brand/laras-logo.jpeg" alt={ALT} style={{ height }} className="w-auto max-w-none select-none" draggable={false} />
    </div>
  );
}
