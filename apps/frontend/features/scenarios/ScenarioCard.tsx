"use client";

import Link from "next/link";
import type { ScenarioOut } from "@/lib/types";
import { Card, ScoreBar, StatusBadge, HudTag } from "@/components/ui";

export function ScenarioCard({
  scenario,
  caseId,
  index,
}: {
  scenario: ScenarioOut;
  caseId: string;
  index: number;
}) {
  return (
    <Link href={`/cases/${caseId}/scenarios/${scenario.id}`} className="block">
      <Card
        className={`p-4 transition hover:border-[#4cc9f0]/60 ${index < 6 ? `enter enter-${index + 1}` : ""} ${
          scenario.is_survivor ? "" : "border-[#3a1530]/50"
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 text-xs">
            <span className="font-mono text-[#4cc9f0]">
              {scenario.hypothesis_label || `H-${index + 1}`}
            </span>
            <StatusBadge status={scenario.status} />
            {!scenario.is_survivor && <StatusBadge status="REJECTED" />}
          </div>
          <ScoreBar score={scenario.score_total} />
        </div>
        <p className="mt-2 line-clamp-2 text-sm text-[#dfe9f5]">{scenario.summary}</p>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-[0.1em] text-[#7e93b3]">
          {scenario.participants?.slice(0, 3).map((p) => (
            <HudTag key={p}>{p}</HudTag>
          ))}
          <span className="ml-auto normal-case tracking-normal text-[#46597a]">
            {scenario.supporting_evidence?.length ?? 0} supporting · {scenario.unknown_count ?? 0} unknown
          </span>
        </div>
        {!scenario.is_survivor && scenario.rejection_reason && (
          <p className="term-danger mt-2 line-clamp-1 text-[11px]">{scenario.rejection_reason}</p>
        )}
      </Card>
    </Link>
  );
}