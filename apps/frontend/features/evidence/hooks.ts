"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { EvidenceOut } from "@/lib/types";

export function useEvidence(caseId: string) {
  return useQuery({
    queryKey: ["evidence", caseId],
    queryFn: async () => (await api.get<EvidenceOut[]>(`/cases/${caseId}/evidence`)).data,
  });
}

export function useUploadEvidence(caseId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: { itemType: string; title: string; text: string; file: File | null }) => {
      const fd = new FormData();
      fd.append("item_type", input.itemType);
      fd.append("title", input.title || input.itemType);
      fd.append("description", input.title || input.itemType);
      fd.append("raw_text", input.text);
      if (input.file) fd.append("file", input.file);
      const { data } = await api.post(`/cases/${caseId}/evidence`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["evidence", caseId] });
      qc.invalidateQueries({ queryKey: ["case", caseId] });
      qc.invalidateQueries({ queryKey: ["dashboard", caseId] });
    },
  });
}
