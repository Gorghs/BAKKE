"use client";

import Link from "next/link";
import { Card, EmptyState, ErrorState, Spinner, StatusBadge } from "@/components/ui";
import { cn, fmtNumber, fmtTime } from "@/lib/utilities";
import { useCases } from "@/features/cases/hooks";

export function CaseBoard() {
  const { data: cases, isLoading, isError } = useCases();

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
      ) : isError ? (
        <ErrorState message="Case files could not be loaded." />
      ) : !cases || cases.length === 0 ? (
        <EmptyState message="No case files on the board. Open a new file from Command." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {cases.map((c, i) => (
            <Link
              key={c.id}
              href={`/cases/${c.id}`}
              className={cn("group block h-full", "enter", `enter-${Math.min(i + 1, 6)}`)}
            >
              <Card className="hover-glow flex h-full flex-col p-4 transition hover:border-[#4cc9f0]/60">
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden="true"
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
                  <p className="mt-1 line-clamp-2 text-xs text-[#7e93b3]">{c.description}</p>
                )}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <StatusBadge status={c.status} />
                  <span className="ml-auto font-mono text-xs tabular-nums text-[#7e93b3]">
                    {fmtNumber(c.evidence_count)} evidence
                  </span>
                </div>
                <div className="mt-2 text-[11px] tracking-[0.08em] text-[#46597a]">
                  {fmtTime(c.created_at)}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
