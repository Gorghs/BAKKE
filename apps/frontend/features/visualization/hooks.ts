"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { VideoSpecOut } from "@/lib/types";
import { useToast } from "@/components/ui";

export function useScenarioVideos(scenarioId: string) {
  return useQuery({
    queryKey: ["videos", scenarioId],
    queryFn: async () =>
      scenarioId
        ? (await api.get<{ id: string; status: string; is_mock: boolean; label_text: string }[]>(
            `/scenarios/${scenarioId}/video`
          )).data
        : [],
    enabled: !!scenarioId,
  });
}

export function useVideoSpec(caseId: string, scenarioId: string) {
  return useQuery({
    queryKey: ["video-spec", caseId, scenarioId],
    queryFn: async () =>
      scenarioId
        ? (await api.get<VideoSpecOut>(`/cases/${caseId}/scenarios/${scenarioId}/spec`)).data
        : null,
    enabled: !!scenarioId,
  });
}

export function useVisualizeScenario(
  caseId: string,
  scenarioId: string,
  invalidateKey: readonly unknown[]
) {
  const qc = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: async () =>
      (await api.post(`/cases/${caseId}/scenarios/${scenarioId}/visualize`)).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: invalidateKey });
    },
    onError: (error) => toast(error.message),
  });
}
