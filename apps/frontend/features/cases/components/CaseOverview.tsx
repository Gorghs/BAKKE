"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ErrorState, SectionTitle, Spinner, Stat } from "@/components/ui";
import { cn, fmtNumber } from "@/lib/utilities";
import { useDashboard } from "@/features/cases/hooks";
import { AnalysisControl } from "@/features/analysis/components/AnalysisControl";
import { ScenarioCard } from "@/features/scenarios/ScenarioCard";

export function CaseOverview() {
  const { id } = useParams<{ id: string }>();

  const { data: dash, isLoading, isError } = useDashboard(id);

  if (isLoading) return <Spinner />;
  if (isError) return <ErrorState message="Case dashboard could not be loaded." />;
  if (!dash) return null;

  const stats: [string, string, string][] = [
    ["Evidence", fmtNumber(dash.evidence_count), "#dfe9f5"],
    ["Facts extracted", fmtNumber(dash.fact_count), "#4cc9f0"],
    ["Timeline events", fmtNumber(dash.timeline_count), "#4cc9f0"],
    ["Constraints", fmtNumber(dash.constraint_count), "#7e93b3"],
    ["Hard constraints", fmtNumber(dash.hard_constraint_count), "#ffb454"],
    ["Conflicts", fmtNumber(dash.conflict_count), dash.conflict_count > 0 ? "#ff5c5c" : "#5ce0a0"],
    ["Forensic anchors", fmtNumber(dash.anchor_count), "#4cc9f0"],
    ["Surviving scenarios", fmtNumber(dash.scenario_survivor_count), "#5ce0a0"],
    ["Rejected scenarios", fmtNumber(dash.scenario_rejected_count), dash.scenario_rejected_count > 0 ? "#ff5c5c" : "#7e93b3"],
    ["Similar cases", fmtNumber(dash.similar_case_count), "#7e93b3"],
    ["Unknown areas", fmtNumber(dash.unknown_area_count), dash.unknown_area_count > 0 ? "#ffb454" : "#7e93b3"],
    ["Videos", fmtNumber(dash.video_count), "#5ce0a0"],
  ];

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {stats.map(([label, value, accent], i) => (
          <div key={label} className={cn("enter", `enter-${Math.min(i + 1, 6)}`)}>
            <Stat label={label} value={value} accent={accent} />
          </div>
        ))}
      </div>

      <AnalysisControl caseId={id} analysisStatus={dash.analysis_status} />

      {dash.scenario_survivor_count > 0 && (
        <section aria-label="Top scenarios" className="enter enter-4">
          <div className="mb-3 flex items-center justify-between">
            <SectionTitle>Top scenarios</SectionTitle>
            <Link href={`/cases/${id}/scenarios`} className="text-[11px] uppercase tracking-[0.16em] text-[#4cc9f0] hover:text-[#9adcf5]">
              View all ▸
            </Link>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {(dash.top_scenarios || []).map((s, i) => (
              <ScenarioCard key={s.id} scenario={s} caseId={id} index={i} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
