"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, cn, fmtNumber } from "@/lib/api";
import type { AnalysisStatus, CaseDashboard } from "@/lib/types";
import { Card, SectionTitle, Spinner, StatusBadge, Stat } from "@/components/ui";
import { ScenarioCard } from "@/features/scenarios/ScenarioCard";

export default function CaseOverviewPage() {
  const { id } = useParams<{ id: string }>();

  const { data: dash, isLoading } = useQuery({
    queryKey: ["dashboard", id],
    queryFn: async () => (await api.get<CaseDashboard>(`/cases/${id}/dashboard`)).data,
  });

  const { data: status, refetch } = useQuery({
    queryKey: ["analysis-status", id],
    queryFn: async () => (await api.get<AnalysisStatus>(`/cases/${id}/analysis/status`)).data,
    refetchInterval: (q) =>
      q.state.data?.status === "PENDING" || q.state.data?.status === "RUNNING" ? 2500 : false,
  });

  const analyzeMutation = useMutation({
    mutationFn: async () => (await api.post<AnalysisStatus>(`/cases/${id}/analyze`)).data,
    onSuccess: () => {
      refetch();
    },
  });

  const running = status?.status === "PENDING" || status?.status === "RUNNING";

  if (isLoading) return <Spinner />;
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

      {dash.analysis_status !== "ANALYZED" && (
        <Card className="hud-scan flex items-center justify-between gap-4 p-4">
          <div>
            <div className="flex items-center gap-2 text-sm font-bold text-[#dfe9f5]">
              Analysis not complete <StatusBadge status={dash.analysis_status} />
            </div>
            <p className="mt-1 text-xs text-[#7e93b3]">
              {running
                ? `Running… ${status?.progress ?? 0}% ${status?.result?.stage ?? ""}`
                : "Run extraction, fusion, iterative reasoning and scoring."}
            </p>
          </div>
          <button
            onClick={() => analyzeMutation.mutate()}
            disabled={running || analyzeMutation.isPending}
            className="btn-cmd shrink-0 rounded-sm px-4 py-2.5"
          >
            {running ? "Analyzing…" : "Analyze case"}
          </button>
        </Card>
      )}

      {dash.scenario_survivor_count > 0 && (
        <section className="enter enter-4">
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
