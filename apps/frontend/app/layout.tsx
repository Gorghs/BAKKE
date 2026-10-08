import type { Metadata } from "next";
import "./globals.css";
import QueryProvider from "@/components/QueryProvider";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "BAKKE Command | Evidence-Constrained Hypothesis Intelligence",
  description:
    "Police command interface. Explore evidence-compatible explanations, eliminate via constraints, and visualize 3D animated scenario reconstructions.",
};

function CommandTicker() {
  const items = [
    "BAKKE NEVER DETERMINES WHAT HAPPENED",
    "SCORES ARE EVIDENCE CONSISTENCY ONLY — NOT PROBABILITY",
    "SIMILAR CASES ARE REFERENCE ONLY — NEVER INJECTED AS FACT",
    "VIDEOS ARE 3D ANIMATED RECONSTRUCTIONS — NOT RECORDED FOOTAGE",
    "EVERY STEP IS AUDITED",
  ];
  const row = items.map((t, i) => (
    <span key={i} className="mx-6 inline-flex items-center gap-2 whitespace-nowrap text-[10px] uppercase tracking-[0.22em] text-[#3f5575]">
      <span className="text-[#4cc9f0]/50">▸</span> {t}
    </span>
  ));
  return (
    <div className="relative overflow-hidden border-b border-[#0d1c38] bg-[#04070f]">
      <div className="ticker">
        <div className="flex">{row}</div>
        <div className="flex">{row}</div>
      </div>
    </div>
  );
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        <div className="cmd-backdrop" />
        <div className="cmd-grid" />
        <div className="cmd-vignette" />
        <div className="scanlines" />
        <QueryProvider>
          <Nav />
          <CommandTicker />
          <main className="relative z-10 mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
          <footer className="relative z-10 mx-auto max-w-7xl px-4 pb-6 sm:px-6 lg:px-8">
            <div className="flex items-center gap-3 border-t border-[#0d1c38] pt-3 text-[9px] uppercase tracking-[0.26em] text-[#3f5575]">
              <span>BAKKE Command Interface</span>
              <span className="flex-1" />
              <span>Evidence Consistency Scores ≠ Probability</span>
              <span className="flex-1" />
              <span className="flex items-center gap-1.5">
                <span className="led-static" style={{ background: "#5ce0a0" }} /> Secure Channel
              </span>
            </div>
          </footer>
        </QueryProvider>
      </body>
    </html>
  );
}
