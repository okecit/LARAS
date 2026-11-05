"use client";

import { Moon, Sun } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { cn } from "./format";

export type ThemeName = "dark" | "light";
export const THEME_KEY = "laras_theme";

/** Nilai warna untuk komponen yang tidak memakai kelas Tailwind (Cytoscape, Recharts, SVG). */
export const PALETTES = {
  dark: {
    bg: "#08122A", panel: "#0C1A3A", panel2: "#12244D", line: "#1C3160", line2: "#2B4580",
    ink: "#E4ECFA", mute: "#98A8CA", dim: "#6A7CA4", accent: "#1EC8E6",
    edge: "#3A5287", nodeBorder: "#08122A", label: "#C7D3EA", highlight: "#E4ECFA", laneA: "#0A1631", laneB: "#0C1A3A",
  },
  light: {
    bg: "#F3F6FC", panel: "#FFFFFF", panel2: "#EAF1FC", line: "#DCE4F2", line2: "#C0CDE6",
    ink: "#0E2557", mute: "#465982", dim: "#6E7FA2", accent: "#088DB2",
    edge: "#A9B8D6", nodeBorder: "#FFFFFF", label: "#0E2557", highlight: "#0E2557", laneA: "#FFFFFF", laneB: "#F1F5FC",
  },
} as const;
export type Palette = (typeof PALETTES)[ThemeName];

type Ctx = { theme: ThemeName; palette: Palette; setTheme: (t: ThemeName) => void; toggle: () => void };
const ThemeCtx = createContext<Ctx | null>(null);

function readInitial(): ThemeName {
  if (typeof document === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeName>("dark");
  useEffect(() => setThemeState(readInitial()), []);
  const setTheme = useCallback((t: ThemeName) => {
    setThemeState(t);
    document.documentElement.dataset.theme = t;
    try {
      window.localStorage.setItem(THEME_KEY, t);
    } catch {
      /* penyimpanan tidak tersedia */
    }
  }, []);
  const toggle = useCallback(() => setTheme(theme === "dark" ? "light" : "dark"), [theme, setTheme]);
  return <ThemeCtx.Provider value={{ theme, palette: PALETTES[theme], setTheme, toggle }}>{children}</ThemeCtx.Provider>;
}

export function useTheme() {
  const v = useContext(ThemeCtx);
  if (!v) throw new Error("useTheme di luar ThemeProvider");
  return v;
}

/** Gaya sumbu/grid/tooltip Recharts sesuai tema. */
export function useChartTheme() {
  const { palette } = useTheme();
  return {
    grid: palette.line,
    tick: { fill: palette.dim, fontSize: 10 },
    tooltip: { contentStyle: { background: palette.panel, border: `1px solid ${palette.line2}`, borderRadius: 8, fontSize: 11, color: palette.ink } },
  };
}

/** Skrip tanpa-kedip: setel tema sebelum React dimuat (tema tersimpan → preferensi sistem → gelap). */
export const themeInitScript = `(function(){try{var t=localStorage.getItem('${THEME_KEY}');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}document.documentElement.dataset.theme=t}catch(e){document.documentElement.dataset.theme='dark'}})();`;

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, setTheme } = useTheme();
  return (
    <div className={cn("flex h-7 items-center rounded-md border border-line2 bg-bg/60 p-0.5", className)} role="group" aria-label="Pilih tema">
      {([["light", Sun, "Terang"], ["dark", Moon, "Gelap"]] as const).map(([t, Icon, label]) => (
        <button key={t} onClick={() => setTheme(t)} title={`Tema ${label.toLowerCase()}`} aria-pressed={theme === t}
          className={cn("flex h-6 items-center gap-1 rounded px-1.5 text-2xs transition-colors",
            theme === t ? "bg-teal text-bg" : "text-mute hover:text-ink")}>
          <Icon className="h-3.5 w-3.5" />
          <span className="hidden 2xl:inline">{label}</span>
        </button>
      ))}
    </div>
  );
}
