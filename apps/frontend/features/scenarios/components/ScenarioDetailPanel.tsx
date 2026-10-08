"use client";

import { useParams } from "next/navigation";
import { Card, EmptyState, ErrorState, SectionTitle, Spinner, StatusBadge } from "@/components/ui";
import { cn } from "@/lib/utilities";
import { useScenario } from "@/features/scenarios/hooks";
import { EvidenceScorePanel } from "@/features/analysis/components/EvidenceScorePanel";
import { ScenarioVideoCard } from "@/features/visualization/components/ScenarioVideoCard";

const EVENT_STYLE: Record<string, string> = {
  KNOWN: "border-l-[#5ce0a0]",
  INFERRED: "border-l-[#4cc9f0]",
  HYPOTHESIZED: "border-l-[#ffb454]",
  UNKNOWN: "border-l-[#46597a]",
};

export function ScenarioDetailPanel() {
  const { id, scenarioId } = useParams<{ id: string; scenarioId: string }>();

  const { data: sc, isLoading, isError } = useScenario(id, scenarioId);

  if (isLoading) return <Spinner />;
  if (isError) return <ErrorState message="Scenario could not be loaded." />;
  if (!sc) return <EmptyState message="Scenario not found." />;

  return (
    <div className="space-y-8">
      <div className="hud-panel hud-corners hud-scan relative rounded-md p-5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-[#4cc9f0]">{sc.hypothesis_label}</span>
          <StatusBadge status={sc.status} />
          {sc.is_survivor ? <StatusBadge status="SURVIVING" /> : <StatusBadge status="REJECTED" />}
        </div>
        <h2 className="mt-2 text-xl font-black leading-snug text-[#dfe9f5]">{sc.summary}</h2>
        {sc.cause_claim && (
          <p className="mt-1 text-xs text-[#7e93b3]">
            Causal claim: <em className="text-[#ffb454]">{sc.cause_claim}</em>
          </p>
        )}
        <div className="mt-3 flex flex-wrap gap-2">
          {sc.participants?.map((p) => (
            <span key={p} className="chip rounded-sm px-2.5 py-1 text-[11px]">
              {p}
            </span>
          ))}
        </div>
      </div>

      {!sc.is_survivor && sc.rejection_reason && (
        <Card className="hud-scan border-[#3a1530]/60 p-4">
          <div className="term-danger text-xs font-bold uppercase tracking-[0.22em]">
            Eliminated
          </div>
          <p className="mt-1 text-sm text-[#ffb0b0]">{sc.rejection_reason}</p>
        </Card>
      )}

      {sc.is_survivor && sc.final_verdict && (
        <Card className="hud-scan p-4">
          <div className="text-xs font-bold uppercase tracking-[0.22em] text-[#7e93b3]">Verdict</div>
          <p className="term mt-1 text-sm">{sc.final_verdict}</p>
        </Card>
      )}

      <div className="grid gap-8 lg:grid-cols-[1fr_340px]">
        <section aria-label="Scenario events" className="enter enter-1">
          <SectionTitle>Scenario events</SectionTitle>
          {!sc.events?.length ? (
            <EmptyState message="No events in this scenario." />
          ) : (
            <div className="space-y-2">
              {sc.events.map((e) => (
                <div
                  key={e.id || e.event_order}
                  className={cn(
                    "hud-panel rounded-r-md border-l-2 p-3",
                    EVENT_STYLE[e.event_type] || "border-l-[#46597a]"
                  )}
                >
                  <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-[#7e93b3]">
                    <span className="chip rounded-sm px-1.5 py-0.5">{e.event_type}</span>
                    {e.timing?.start && (
                      <span className="font-mono text-[#4cc9f0]">
                        {e.timing.start}
                        {e.timing.end ? `–${e.timing.end}` : ""}
                      </span>
                    )}
                    {e.location && <span>@ {e.location}</span>}
                  </div>
                  <p className="mt-1 text-sm text-[#dfe9f5]">{e.description}</p>
                  {(e.evidence_links?.length || 0) > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1 text-[10px] tracking-[0.08em] text-[#46597a]">
                      {e.evidence_links.map((s) => (
                        <span key={s} className="rounded-sm border border-[#0d1c38] bg-[#060b16] px-1">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {sc.unknown?.length ? (
            <div className="mt-6">
              <SectionTitle>Unknowns</SectionTitle>
              <Card className="hud-scan space-y-1 p-4">
                {sc.unknown.map((u, i) => (
                  <p key={i} className="text-xs text-[#7e93b3]">
                    <span aria-hidden="true" className="term-warn mr-1">▸</span>
                    {u}
                  </p>
                ))}
              </Card>
            </div>
          ) : null}
        </section>

        <div className="space-y-6">
          <EvidenceScorePanel score={sc.score_total} breakdown={sc.score_breakdown || {}} />

          <section aria-label="Evidence support" className="enter enter-3">
            <SectionTitle>Evidence support</SectionTitle>
            <Card className="hud-sweep p-4 text-sm">
              <div className="flex justify-between border-b border-[#0d1c38] pb-2">
                <span className="text-[#5ce0a0]">Supporting</span>
                <span className="tabular-nums">{sc.supporting_evidence?.length ?? 0}</span>
              </div>
              <div className="flex justify-between py-2">
                <span className="text-[#ff5c5c]">Contradicting</span>
                <span className="tabular-nums">{sc.contradicting_evidence?.length ?? 0}</span>
              </div>
              <div className="flex justify-between border-t border-[#0d1c38] pt-2">
                <span className="text-[#ffb454]">Unknown periods</span>
                <span className="tabular-nums">{sc.unknown_count ?? 0}</span>
              </div>
            </Card>
          </section>

          <ScenarioVideoCard
            caseId={id}
            scenarioId={scenarioId}
            isSurvivor={sc.is_survivor}
            video={sc.video}
          />
        </div>
      </div>

      {sc.similar_cases?.length ? (
        <section aria-label="Analogical reference cases" className="enter enter-5">
          <SectionTitle>Analogical reference cases</SectionTitle>
          <p className="mb-2 text-[10px] uppercase tracking-[0.14em] text-[#46597a]">
            Reference material only — conclusions are never transferred as fact.
          </p>
          <div className="grid gap-3 md:grid-cols-2">
            {sc.similar_cases.map((s) => (
              <Card key={s.reference_label} className="hud-sweep p-3">
                <div className="flex items-center gap-2 text-xs">
                  <span className="font-mono text-[#4cc9f0]">{s.reference_label}</span>
                  <span className="chip rounded-sm px-1.5 py-0.5">similarity {s.similarity}</span>
                </div>
                <p className="mt-1 text-sm text-[#dfe9f5]">{s.title}</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {s.relevant_patterns?.map((p) => (
                    <span key={p} className="chip rounded-sm px-1.5 py-0.5 text-[10px]">
                      {p}
                    </span>
                  ))}
                </div>
              </Card>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
