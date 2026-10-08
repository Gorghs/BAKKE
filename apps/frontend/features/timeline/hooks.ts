"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { AnchorOut, ConflictOut, TimelineEventOut } from "@/lib/types";

interface ConstraintRow {
  constraint_id: string;
  type: string;
  severity: string;
  description: string;
}

export function useTimeline(caseId: string) {
  return useQuery({
    queryKey: ["timeline", caseId],
    queryFn: async () => (await api.get<TimelineEventOut[]>(`/cases/${caseId}/timeline`)).data,
  });
}

export function useAnchors(caseId: string) {
  return useQuery({
    queryKey: ["anchors", caseId],
    queryFn: async () => (await api.get<AnchorOut[]>(`/cases/${caseId}/anchors`)).data,
  });
}

export function useConflicts(caseId: string) {
  return useQuery({
    queryKey: ["conflicts", caseId],
    queryFn: async () => (await api.get<ConflictOut[]>(`/cases/${caseId}/conflicts`)).data,
  });
}

export function useConstraints(caseId: string) {
  return useQuery({
    queryKey: ["constraints", caseId],
    queryFn: async () => (await api.get<ConstraintRow[]>(`/cases/${caseId}/constraints`)).data,
  });
}
