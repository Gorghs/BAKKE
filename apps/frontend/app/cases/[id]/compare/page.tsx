"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { api, cn } from "@/lib/api";
import type { ScenarioOut } from "@/lib/types";
import { Card, EmptyState, SectionTitle, Spinner } from "@/components/ui";

interface CompareResult {
  case_id: string;
  scenarios: ScenarioOut[];
  shared: string[];
  differences: string[];
  discriminating: { pair: string[]; note: string }[];
}

export default function ComparePage() {
  const { id } = useParams<{ id: string }>();
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [loading, setLoading] = useState(false);

  const { data: scenarios, isLoading } = useQuery({
    queryKey: ["scenarios", id],
    queryFn: async () => (await api.get<ScenarioOut[]>(`/cases/${id}/scenarios`)).data,
  });

  const survivors = (scenarios || []).filter((s) => s.is_survivor);

  function toggle(sid: string) {
    setSelected((prev) =>
      prev.includes(sid) ? prev.filter((x) => x !== sid) : prev.length < 4 ? [...prev, sid] : prev
    );
    setResult(null);
  }

  async function compare() {
    setLoading(true);
    try {
      const { data } = await api.post<CompareResult>("/scenarios/compare", {
        scenario_ids: selected,
      });
      setResult(data);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="term text-[10px] uppercase tracking-[0.3em]">{"// scenario comparison"}</p>
        <h2 className="mt-1 text-lg font-black uppercase tracking-[0.1em] text-[#dfe9f5]">
          Compare Scenarios<span className="text-[#4cc9f0]">.</span>
        </h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[#7e93b3]">
          Select 2–4 surviving scenarios to compare shared and differing evidence, and to identify
          evidence that could discriminate between them. Comparison is descriptive — not a ranking
          of truth.
        </p>
      </div>

      {isLoading ? (
        <Spinner />
      ) : survivors.length < 2 ? (
        <EmptyState message="At least two surviving scenarios are required to compare." />
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            {survivors.map((s, i) => {
              const active = selected.includes(s.id);
              return (
                <button
                  key={s.id}
                  onClick={() => toggle(s.id)}
                  className={cn(
                    "enter",
                    `enter-${Math.min(i + 1, 6)}`,
                    "hud-panel hud-corners rounded-md p-4 text-left transition",
                    active
                      ? "border-[#4cc9f0]/80 shadow-[0_0_16px_rgba(76,201,240,0.25)]"
                      : "hover:border-[#4cc9f0]/40"
                  )}
                >
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] text-[#7e93b3]">
                    <span
                      className="led-static"
                      style={{ background: active ? "#4cc9f0" : "#46597a" }}
                    />
                    <span className="font-mono text-[#4cc9f0]">{s.hypothesis_label}</span>
                    <span className="ml-auto text-xs">score {s.score_total}</span>
                  </div>
                  <p className="mt-1.5 line-clamp-2 text-sm text-[#dfe9f5]">{s.summary}</p>
                </button>
              );
            })}
          </div>

          <button
            onClick={compare}
            disabled={selected.length < 2 || loading}
            className="btn-cmd rounded-sm px-4 py-2.5"
          >
            {loading ? "Comparing…" : `Compare ${selected.length} scenarios`}
          </button>

          {result && (
            <>
              <section className="enter enter-3">
                <SectionTitle>Shared evidence</SectionTitle>
                {result.shared.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {result.shared.map((s) => (
                      <span
                        key={s}
                        className="rounded-sm border border-[#5ce0a0]/30 bg-[#5ce0a0]/5 px-2 py-1 text-[11px] text-[#9be9c2]"
                      >
                        ▸ {s}
                      </span>
                    ))}
                  </div>
                ) : (
                  <EmptyState message="No shared evidence across the selection." />
                )}
              </section>

              <section className="enter enter-4">
                <SectionTitle>Differing evidence</SectionTitle>
                {result.differences.length ? (
                  <div className="flex flex-wrap gap-1.5">
                    {result.differences.map((s) => (
                      <span
                        key={s}
                        className="rounded-sm border border-[#ffb454]/30 bg-[#ffb454]/5 px-2 py-1 text-[11px] text-[#ffce8a]"
                      >
                        <span className="mr-1">◈</span>
                        {s}
                      </span>
                    ))}
                  </div>
                ) : (
                  <EmptyState message="The selected scenarios rely on the same evidence." />
                )}
              </section>

              <section className="enter enter-5">
                <SectionTitle>Potentially discriminating evidence</SectionTitle>
                <div className="space-y-2">
                  {result.discriminating.map((d, i) => (
                    <Card key={i} className="hud-scan p-3">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="font-mono text-[#4cc9f0]">{d.pair.join(" vs ")}</span>
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-[#a9bcd9]">{d.note}</p>
                    </Card>
                  ))}
                </div>
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}