"use client";

import { Card, SectionTitle } from "@/components/ui";

export function EvidenceScorePanel({
  score,
  breakdown,
}: {
  score: number;
  breakdown: Record<string, unknown>;
}) {
  const rows = Object.entries(breakdown).filter(([k]) => k !== "note" && typeof k === "string");

  return (
    <section aria-label="Evidence consistency" className="enter enter-2">
      <SectionTitle>Evidence consistency</SectionTitle>
      <Card className="hud-scan p-4">
        <div className="flex items-baseline gap-2">
          <span className="text-4xl font-black tabular-nums text-[#4cc9f0]" style={{ textShadow: "0 0 14px rgba(76,201,240,0.4)" }}>
            {score}
          </span>
          <span className="text-sm text-[#46597a]">/ 100</span>
        </div>
        <p className="mt-2 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-[#46597a]">
          {(breakdown.note as string) ||
            "Evidence Consistency Score - consistency with currently available evidence, NOT probability."}
        </p>
        <div className="mt-3 space-y-1.5 border-t border-[#0d1c38] pt-3">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between text-xs">
              <span className="uppercase tracking-[0.1em] text-[#7e93b3]">{k.replace(/_/g, " ")}</span>
              <span className="tabular-nums text-[#a9bcd9]">{String(v)}</span>
            </div>
          ))}
        </div>
      </Card>
    </section>
  );
}
