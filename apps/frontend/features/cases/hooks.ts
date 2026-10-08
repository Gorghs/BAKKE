"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api/client";
import type { CaseDashboard, CaseOut } from "@/lib/types";

export function useCases() {
  return useQuery({
    queryKey: ["cases"],
    queryFn: async () => (await api.get<CaseOut[]>("/cases")).data,
  });
}

export function useCase(caseId: string) {
  return useQuery({
    queryKey: ["case", caseId],
    queryFn: async () => (await api.get<CaseOut>(`/cases/${caseId}`)).data,
  });
}

export function useDashboard(caseId: string) {
  return useQuery({
    queryKey: ["dashboard", caseId],
    queryFn: async () => (await api.get<CaseDashboard>(`/cases/${caseId}/dashboard`)).data,
  });
}

export function useCreateCase() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: async (input: { name: string; description: string }) => {
      const { data } = await api.post<CaseOut>("/cases", {
        name: input.name,
        description: input.description,
        tags: [],
      });
      return data;
    },
    onSuccess: (c) => {
      qc.invalidateQueries({ queryKey: ["cases"] });
      router.push(`/cases/${c.id}`);
    },
  });
}
