"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { api, cn } from "@/lib/api";
import type { ScenarioOut } from "@/lib/types";
import { EmptyState, SectionTitle, Spinner } from "@/components/ui";
import { ScenarioCard } from "@/features/scenarios/ScenarioCard";

const TOP_N = 10;

export default function ScenariosPage() {
  const { id } = useParams<{ id: string }>();
  const [showMore, setShowMore] = useState(false);
  const [filter, setFilter] = useState<"all" | "surviving" | "rejected">("surviving");

  const { data: scenarios, isLoading } = useQuery({
    queryKey: ["scenarios", id],
    queryFn: async () => (await api.get<ScenarioOut[]>(`/cases/${id}/scenarios`)).data,
  });

  const survivors = useMemo(() => (scenarios || []).filter((s) => s.is_survivor), [scenarios]);
  const rejected = useMemo(() => (scenarios || []).filter((s) => !s.is_survivor), [scenarios]);

  const visible = filter === "surviving" ? survivors : filter === "rejected" ? rejected : scenarios || [];
  const top = visible.slice(0, TOP_N);
  const rest = visible.slice(TOP_N);
  const showRest = showMore || filter !== "surviving";

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="term text-[10px] uppercase tracking-[0.3em]">{"// hypothesis candidates"}</p>
          <h2 className="mt-1 text-lg font-black uppercase tracking-[0.1em] text-[#dfe9f5]">
            Scenario Candidates<span className="text-[#4cc9f0]">.</span>
          </h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[#7e93b3]">
            Scores are <span className="text-[#dfe9f5]">evidence consistency</span> scores, not
            probabilities — they measure fit with available evidence, never a verdict. Eliminated
            candidates are retained with their reasons.
          </p>
        </div>
        <div className="flex gap-1 rounded-sm border border-[#14305c] bg-[#070d1c] p-1 text-[10px] uppercase tracking-[0.14em]">
          {(["surviving", "rejected", "all"] as const).map((f) => (
            <button
              key={f}
              onClick={() => {
                setFilter(f);
                setShowMore(false);
              }}
              className={cn(
                "rounded-sm px-3 py-1.5 transition",
                filter === f
                  ? "bg-[#0b1428] text-[#4cc9f0] shadow-[inset_0_0_8px_rgba(76,201,240,0.15)]"
                  : "text-[#7e93b3] hover:text-[#dfe9f5]"
              )}
            >
              {f === "surviving"
                ? `Surviving (${survivors.length})`
                : f === "rejected"
                  ? `Rejected (${rejected.length})`
                  : `All (${scenarios?.length ?? 0})`}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <Spinner />
      ) : !visible.length ? (
        <EmptyState message="No scenarios. Run analysis to generate hypothesis candidates." />
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-2">
            {top.map((s, i) => (
              <ScenarioCard key={s.id} scenario={s} caseId={id} index={i} />
            ))}
          </div>

          {rest.length > 0 && !showRest && (
            <div className="flex justify-center">
              <button
                onClick={() => setShowMore(true)}
                className="btn-cmd rounded-sm px-4 py-2"
              >
                Show {rest.length} more scenario{rest.length > 1 ? "s" : ""}
              </button>
            </div>
          )}

          {showRest && (
            <div className="grid gap-3 md:grid-cols-2">
              {rest.map((s, i) => (
                <ScenarioCard key={s.id} scenario={s} caseId={id} index={TOP_N + i} />
              ))}
            </div>
          )}
        </>
      )}

      {rejected.length > 0 && filter === "surviving" && (
        <section className="hud-panel hud-corners relative rounded-md p-4">
          <div className="mb-2 flex items-center gap-2">
            <SectionTitle>Eliminated candidates</SectionTitle>
            <span className="text-[10px] uppercase tracking-[0.14em] text-[#46597a]">
              {rejected.length} rejected with documented reasons
            </span>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            {rejected.slice(0, 6).map((s, i) => (
              <ScenarioCard key={s.id} scenario={s} caseId={id} index={i} />
            ))}
          </div>
          {rejected.length > 6 && (
            <p className="mt-2 text-center text-[10px] uppercase tracking-[0.16em] text-[#46597a]">
              View all {rejected.length} eliminated candidates in the “Rejected” filter.
            </p>
          )}
        </section>
      )}
    </div>
  );
}
