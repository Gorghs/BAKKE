"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { AuditEventOut } from "@/lib/types";

export function useAuditEvents(caseId: string) {
  return useQuery({
    queryKey: ["audit", caseId],
    queryFn: async () => (await api.get<AuditEventOut[]>(`/cases/${caseId}/audit`)).data,
  });
}
