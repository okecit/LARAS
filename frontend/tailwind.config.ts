import type { Config } from "tailwindcss";

// Warna inti dibaca dari variabel CSS (lihat app/globals.css) agar tema gelap/terang dapat ditukar.
const v = (name: string) => `rgb(var(--c-${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        panel: v("panel"),
        panel2: v("panel2"),
        line: v("line"),
        line2: v("line2"),
        ink: v("ink"),
        mute: v("mute"),
        dim: v("dim"),
        teal: v("teal"),
        cyan: v("cyan"),
        purple: v("purple"),
        amber: v("amber"),
        blue: v("blue"),
        danger: v("danger"),
      },
      fontFamily: {
        sans: ["Inter", "Segoe UI", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Cascadia Code", "ui-monospace", "monospace"],
      },
      fontSize: { "2xs": ["0.6875rem", "1rem"] },
      boxShadow: { glow: "0 0 0 1px rgb(var(--c-teal) / .35), 0 0 24px -6px rgb(var(--c-teal) / .45)" },
      backgroundImage: { brand: "linear-gradient(90deg, #1EC8E6 0%, #2F6FE0 50%, #7B3FE4 100%)" },
    },
  },
  plugins: [],
};
export default config;
