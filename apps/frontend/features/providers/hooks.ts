"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { ProviderStatus } from "@/lib/types";

export function useProviders(refetchInterval?: number) {
  return useQuery({
    queryKey: ["providers"],
    queryFn: async () => (await api.get<ProviderStatus>("/providers")).data,
    staleTime: 30_000,
    refetchInterval,
  });
}
