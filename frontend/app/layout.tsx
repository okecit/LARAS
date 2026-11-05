import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LARAs — Youth Social Behavior Network Analytics",
  description: "Lacak Aktivitas Remaja di Ruang Siber: pemetaan jaringan, analisis penyebaran, pemahaman perilaku.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="font-sans">{children}</body>
    </html>
  );
}
