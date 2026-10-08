"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, cn, fmtTime, fmtNumber } from "@/lib/api";
import type { CaseOut } from "@/lib/types";
import { EmptyState, Spinner, StatusBadge } from "@/components/ui";

export default function CasesPage() {
  const { data: cases, isLoading } = useQuery({
    queryKey: ["cases"],
    queryFn: async () => (await api.get<CaseOut[]>("/cases")).data,
  });

  const analyzed = (cases || []).filter((c) => c.status === "ANALYZED").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="term text-[10px] uppercase tracking-[0.3em]">{"// case files"}</p>
          <h1 className="mt-1 text-2xl font-black uppercase tracking-[0.12em] text-[#dfe9f5]">
            Case Board<span className="text-[#4cc9f0]">.</span>
          </h1>
          <p className="mt-1 text-xs text-[#7e93b3]">
            Every case is explored as evidence-compatible explanations, never as a verdict.
          </p>
        </div>
        <span className="chip rounded-sm px-2.5 py-1.5 text-[10px]">
          {fmtNumber(analyzed)} analyzed / {fmtNumber(cases?.length ?? 0)} on board
        </span>
      </div>

      {isLoading ? (
        <Spinner />
      ) : !cases || cases.length === 0 ? (
        <EmptyState message="No case files on the board. Open a new file from Command." />
      ) : (
        <div className="overflow-hidden rounded-md border border-[#14305c]/70">
          <div className="grid grid-cols-[1fr_110px_90px_150px] bg-[#070d1c] px-4 py-2 text-[9px] uppercase tracking-[0.22em] text-[#46597a]">
            <span>Case file</span>
            <span>Status</span>
            <span className="text-right">Evidence</span>
            <span className="text-right">Opened</span>
          </div>
          <div className="divide-y divide-[#0d1c38]">
            {cases.map((c, i) => (
              <Link
                key={c.id}
                href={`/cases/${c.id}`}
                className={cn(
                  "group grid grid-cols-[1fr_110px_90px_150px] items-center bg-[#060b16]/80 px-4 py-3 transition hover:bg-[#0b1428]",
                  "enter",
                  `enter-${Math.min(i + 1, 6)}`
                )}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className="led-static shrink-0"
                      style={{
                        background:
                          c.status === "ANALYZED" ? "#5ce0a0" : c.status === "DRAFT" ? "#4cc9f0" : "#ffb454",
                      }}
                    />
                    <span className="truncate text-sm font-bold text-[#dfe9f5] group-hover:text-[#4cc9f0]">
                      {c.name}
                    </span>
                  </div>
                  {c.description && (
                    <div className="mt-0.5 truncate pl-3 text-xs text-[#7e93b3]">{c.description}</div>
                  )}
                </div>
                <div>
                  <StatusBadge status={c.status} />
                </div>
                <div className="text-right font-mono text-xs tabular-nums text-[#7e93b3]">
                  {fmtNumber(c.evidence_count)}
                </div>
                <div className="text-right text-[11px] tracking-[0.08em] text-[#46597a]">
                  {fmtTime(c.created_at)}
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
