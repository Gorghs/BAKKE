"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { CaseNav } from "@/components/CaseNav";
import { Led, StatusBadge } from "@/components/ui";
import { api } from "@/lib/api";
import type { CaseOut } from "@/lib/types";

export default function CaseLayout({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const { data: cs } = useQuery({
    queryKey: ["case", id],
    queryFn: async () => (await api.get<CaseOut>(`/cases/${id}`)).data,
  });

  const statusColor =
    cs?.status === "ANALYZED" ? "#5ce0a0" : cs?.status === "DRAFT" ? "#4cc9f0" : "#ffb454";

  return (
    <div className="space-y-6">
      <section className="hud-panel hud-corners hud-sweep relative rounded-md p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[10px] uppercase tracking-[0.3em] text-[#46597a]">Case file</span>
          <span className="font-mono text-xs text-[#4cc9f0]">#{id?.slice(0, 8)}</span>
          <Led color={statusColor} />
          <h1 className="text-xl font-black uppercase tracking-[0.08em] text-[#dfe9f5]">
            {cs?.name ?? "Loading…"}
          </h1>
          <StatusBadge status={cs?.status ?? ""} />
        </div>
        {cs?.description && (
          <p className="mt-2 max-w-3xl text-xs leading-relaxed text-[#7e93b3]">{cs.description}</p>
        )}
        {cs?.tags?.length ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {cs.tags.map((t) => (
              <span key={t} className="chip rounded-sm px-2 py-0.5 uppercase tracking-[0.12em]">
                {t}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      <CaseNav />

      {children}
    </div>
  );
}
