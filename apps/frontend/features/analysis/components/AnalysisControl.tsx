"use client";

import { Card, StatusBadge, useToast } from "@/components/ui";
import { useAnalysisStatus, useAnalyzeCase } from "@/features/analysis/hooks";

export function AnalysisControl({
  caseId,
  analysisStatus,
}: {
  caseId: string;
  analysisStatus: string;
}) {
  const toast = useToast();
  const statusQuery = useAnalysisStatus(caseId);
  const analyzeMutation = useAnalyzeCase(caseId, statusQuery.refetch);

  const status = statusQuery.data;
  const running = status?.status === "PENDING" || status?.status === "RUNNING";

  if (analysisStatus === "ANALYZED") return null;

  return (
    <Card className="hud-scan flex items-center justify-between gap-4 p-4">
      <div>
        <div className="flex items-center gap-2 text-sm font-bold text-[#dfe9f5]">
          Analysis not complete <StatusBadge status={analysisStatus} />
        </div>
        <p aria-live="polite" className="mt-1 text-xs text-[#7e93b3]">
          {running
            ? `Running… ${status?.progress ?? 0}% ${status?.result?.stage ?? ""}`
            : "Run extraction, fusion, iterative reasoning and scoring."}
        </p>
        {statusQuery.isError && (
          <p className="term-danger mt-1 text-xs">Analysis status unavailable.</p>
        )}
      </div>
      <button
        onClick={() =>
          analyzeMutation.mutate(undefined, { onError: (err) => toast(err.message) })
        }
        disabled={running || analyzeMutation.isPending}
        className="btn-cmd shrink-0 rounded-sm px-4 py-2.5"
      >
        {running ? "Analyzing…" : "Analyze case"}
      </button>
    </Card>
  );
}
