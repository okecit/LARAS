import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const COMMUNITY_COLORS = [
  "#9B6DF6", "#F5A524", "#2F6FE0", "#1EC8E6", "#F472B6", "#22D3EE", "#FB923C", "#A3E635",
  "#818CF8", "#F87171", "#34D399", "#E879F9",
];
export const communityColor = (c: number) => (c < 0 ? "#7A8AA6" : COMMUNITY_COLORS[c % COMMUNITY_COLORS.length]);

export const PLATFORM_COLORS: Record<string, string> = {
  tiktok: "#22D3EE", instagram: "#C084FC", youtube: "#F87171", x: "#7F8FA9", lainnya: "#94A3B8",
};
export const PLATFORM_NAMES: Record<string, string> = {
  tiktok: "TikTok", instagram: "Instagram", youtube: "YouTube", x: "X", lainnya: "Lainnya",
};

export const EVIDENCE_COLORS: Record<string, string> = {
  kemiripan: "#7A8AA6",
  kemungkinan_replikasi: "#FBBF24",
  replikasi_didukung: "#FB923C",
  atribusi_terkonfirmasi: "#2DD4BF",
};
export const EVIDENCE_LABELS: Record<string, string> = {
  kemiripan: "Konten serupa",
  kemungkinan_replikasi: "Kemungkinan replikasi",
  replikasi_didukung: "Replikasi didukung",
  atribusi_terkonfirmasi: "Atribusi terkonfirmasi",
};

export const CONTEXT_COLORS: Record<string, string> = {
  kandidat_berbahaya: "#F87171",
  kontra_narasi: "#2DD4BF",
  berita: "#60A5FA",
  edukasi: "#A3E635",
  satire: "#E879F9",
  pencegahan: "#34D399",
  netral: "#7A8AA6",
  tidak_jelas: "#94A3B8",
};
export const CONTEXT_LABELS: Record<string, string> = {
  kandidat_berbahaya: "Kandidat berbahaya",
  kontra_narasi: "Kontra-narasi",
  berita: "Pemberitaan",
  edukasi: "Edukasi",
  satire: "Satire",
  pencegahan: "Pencegahan",
  netral: "Netral",
  tidak_jelas: "Tidak jelas",
};

export const INTERACTION_LABELS: Record<string, string> = {
  komentar: "Komentar", balasan: "Balasan", bagikan: "Bagikan", kutipan: "Kutipan", remix: "Remix/duet",
  sebutan: "Sebutan", membuat: "Membuat konten",
};

export const RELATION_LABELS: Record<string, string> = {
  balasan_dari: "Balasan", repost_dari: "Repost", kutipan_dari: "Kutipan", remix_dari: "Remix/duet/stitch",
  lintas_platform: "Lintas platform", kemiripan: "Kemiripan",
};

export const ACCOUNT_LABELS: Record<string, string> = {
  individu: "Individu", media: "Media", organisasi: "Organisasi", lembaga_pendidikan: "Lembaga pendidikan",
  kreator: "Kreator", tidak_diketahui: "Tidak diketahui",
};

export const VALIDATION_LABELS: Record<string, string> = {
  belum_ditinjau: "Belum ditinjau", valid: "Valid", ditolak: "Ditolak", direvisi: "Direvisi",
};

const dtf = new Intl.DateTimeFormat("id-ID", { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Jakarta" });
const dttf = new Intl.DateTimeFormat("id-ID", {
  day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta",
});

export const fmtDate = (s?: string | null) => (s ? dtf.format(new Date(s)) : "—");
export const fmtDateTime = (s?: string | null) => (s ? `${dttf.format(new Date(s))} WIB` : "—");
export const fmtNum = (n?: number | null, d = 0) =>
  n === undefined || n === null ? "—" : n.toLocaleString("id-ID", { maximumFractionDigits: d, minimumFractionDigits: d });
export const fmtMetric = (n?: number) => (n === undefined ? "—" : n >= 10 ? fmtNum(n, 0) : n.toFixed(4));
export const fmtHours = (h?: number | null) => {
  if (h === undefined || h === null) return "—";
  if (Math.abs(h) < 48) return `${fmtNum(h, 1)} jam`;
  return `${fmtNum(h / 24, 1)} hari`;
};
