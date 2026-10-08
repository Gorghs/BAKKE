"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { CompareResult, ScenarioDetail, ScenarioOut } from "@/lib/types";

export function useScenarios(caseId: string) {
  return useQuery({
    queryKey: ["scenarios", caseId],
    queryFn: async () => (await api.get<ScenarioOut[]>(`/cases/${caseId}/scenarios`)).data,
  });
}

export function useScenario(caseId: string, scenarioId: string) {
  return useQuery({
    queryKey: ["scenario", caseId, scenarioId],
    queryFn: async () =>
      (await api.get<ScenarioDetail>(`/cases/${caseId}/scenarios/${scenarioId}`)).data,
  });
}

export function useCompareScenarios() {
  return useMutation({
    mutationFn: async (scenarioIds: string[]) => {
      const { data } = await api.post<CompareResult>("/scenarios/compare", {
        scenario_ids: scenarioIds,
      });
      return data;
    },
  });
}
