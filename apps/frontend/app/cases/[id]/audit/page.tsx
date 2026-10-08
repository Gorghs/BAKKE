"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api, cn, fmtTime } from "@/lib/api";
import type { AuditEventOut } from "@/lib/types";
import { EmptyState, Spinner } from "@/components/ui";

export default function AuditPage() {
  const { id } = useParams<{ id: string }>();

  const { data: audit, isLoading } = useQuery({
    queryKey: ["audit", id],
    queryFn: async () => (await api.get<AuditEventOut[]>(`/cases/${id}/audit`)).data,
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="term text-[10px] uppercase tracking-[0.3em]">{"// activity log"}</p>
        <h2 className="mt-1 text-lg font-black uppercase tracking-[0.1em] text-[#dfe9f5]">
          Audit Trail<span className="text-[#4cc9f0]">.</span>
        </h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-[#7e93b3]">
          Every step — extraction, fusion, constraint checks, adversarial review, scoring, ranking,
          video generation — is recorded with its agent, provider and source objects.
        </p>
      </div>

      {isLoading ? (
        <Spinner />
      ) : !audit || audit.length === 0 ? (
        <EmptyState message="No audit events recorded." />
      ) : (
        <div className="space-y-1.5">
          {audit.map((a, i) => (
            <div
              key={a.id}
              className={cn(
                "hud-panel hud-sweep grid grid-cols-[120px_1fr_auto] items-start gap-3 rounded-md px-3 py-2",
                "enter",
                `enter-${Math.min(i + 1, 6)}`
              )}
            >
              <div className="font-mono text-[10px] text-[#46597a]">{fmtTime(a.timestamp)}</div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-sm border border-[#4cc9f0]/30 bg-[#4cc9f0]/5 px-1.5 py-0.5 text-[10px] uppercase tracking-[0.14em] text-[#4cc9f0]">
                    {a.action}
                  </span>
                  <span className="text-[10px] uppercase tracking-[0.14em] text-[#7e93b3]">{a.agent}</span>
                  {a.provider && <span className="text-[10px] uppercase tracking-[0.14em] text-[#46597a]">via {a.provider}</span>}
                </div>
                <p className="mt-0.5 text-xs text-[#a9bcd9]">{a.summary}</p>
              </div>
              <span className="led-static mt-1" style={{ background: i % 2 ? "#4cc9f0" : "#5ce0a0" }} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}