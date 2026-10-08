"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { AnalysisStatus } from "@/lib/types";

export function useAnalysisStatus(caseId: string) {
  return useQuery({
    queryKey: ["analysis-status", caseId],
    queryFn: async () => (await api.get<AnalysisStatus>(`/cases/${caseId}/analysis/status`)).data,
    refetchInterval: (q) =>
      q.state.data?.status === "PENDING" || q.state.data?.status === "RUNNING" ? 2500 : false,
  });
}

export function useAnalyzeCase(caseId: string, refetch: () => void) {
  return useMutation({
    mutationFn: async () => (await api.post<AnalysisStatus>(`/cases/${caseId}/analyze`)).data,
    onSuccess: () => {
      refetch();
    },
  });
}
