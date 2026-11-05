import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0B1220",
        panel: "#0F172A",
        panel2: "#131D33",
        line: "#1E2A44",
        line2: "#2A3A5C",
        ink: "#E2E8F0",
        mute: "#94A3B8",
        dim: "#64748B",
        teal: "#2DD4BF",
        cyan: "#22D3EE",
        purple: "#A78BFA",
        amber: "#FBBF24",
        blue: "#60A5FA",
        danger: "#F87171",
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "ui-monospace", "monospace"],
      },
      fontSize: { "2xs": ["0.6875rem", "1rem"] },
      boxShadow: { glow: "0 0 0 1px rgba(45,212,191,.35), 0 0 24px -6px rgba(34,211,238,.45)" },
    },
  },
  plugins: [],
};
export default config;
