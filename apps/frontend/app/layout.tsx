import type { Metadata } from "next";
import "./globals.css";
import QueryProvider from "@/components/layout/QueryProvider";
import Nav from "@/components/layout/Nav";
import { CommandTicker } from "@/components/layout/CommandTicker";
import { ToastProvider } from "@/components/ui";

export const metadata: Metadata = {
  title: "BAKKE Command | Evidence-Constrained Hypothesis Intelligence",
  description:
    "Police command interface. Explore evidence-compatible explanations, eliminate via constraints, and visualize 3D animated scenario reconstructions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        <div aria-hidden="true" className="cmd-backdrop" />
        <div aria-hidden="true" className="cmd-grid" />
        <div aria-hidden="true" className="cmd-vignette" />
        <div aria-hidden="true" className="scanlines" />
        <QueryProvider>
          <ToastProvider>
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
          </ToastProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
