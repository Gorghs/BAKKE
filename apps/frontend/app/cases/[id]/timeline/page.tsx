"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { api, cn } from "@/lib/api";
import type { AnchorOut, ConflictOut, TimelineEventOut } from "@/lib/types";
import { Card, EmptyState, SectionTitle, Spinner, SeverityDot, StatusBadge } from "@/components/ui";

function timeStr(e: TimelineEventOut): string {
  if (e.time_label) return e.time_label;
  if (e.time_start && e.time_end) return `${e.time_start}–${e.time_end}`;
  if (e.time_start) return e.time_start;
  return e.time_type;
}

export default function TimelinePage() {
  const { id } = useParams<{ id: string }>();

  const { data: timeline, isLoading } = useQuery({
    queryKey: ["timeline", id],
    queryFn: async () => (await api.get<TimelineEventOut[]>(`/cases/${id}/timeline`)).data,
  });

  const { data: anchors } = useQuery({
    queryKey: ["anchors", id],
    queryFn: async () => (await api.get<AnchorOut[]>(`/cases/${id}/anchors`)).data,
  });

  const { data: conflicts } = useQuery({
    queryKey: ["conflicts", id],
    queryFn: async () => (await api.get<ConflictOut[]>(`/cases/${id}/conflicts`)).data,
  });

  const { data: constraints } = useQuery({
    queryKey: ["constraints", id],
    queryFn: async () =>
      (await api.get<{ constraint_id: string; type: string; severity: string; description: string }[]>(
        `/cases/${id}/constraints`
      )).data,
  });

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
      <section className="enter enter-1">
        <div className="mb-3 flex items-center justify-between">
          <SectionTitle>Timeline</SectionTitle>
          <span className="text-[10px] uppercase tracking-[0.18em] text-[#46597a]">
            {timeline?.length ?? 0} events
          </span>
        </div>
        {isLoading ? (
          <Spinner />
        ) : !timeline || timeline.length === 0 ? (
          <EmptyState message="No timeline events extracted. Run analysis first." />
        ) : (
          <div className="relative space-y-0 border-l border-[#14305c] pl-5">
            {timeline.map((e, i) => (
              <div key={e.event_id} className={cn("relative pb-6", "enter", `enter-${Math.min(i + 1, 6)}`)}>
                <span
                  className="absolute -left-[26px] top-1.5 grid h-3 w-3 place-items-center"
                  style={{ color: e.certainty === "KNOWN" ? "#5ce0a0" : "#ffb454" }}
                >
                  <span className="h-3 w-3 rounded-full border-2 border-[#0b1428] bg-current shadow-[0_0_8px_currentColor]" />
                </span>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-[#4cc9f0]">{timeStr(e)}</span>
                  <SeverityDot level={e.certainty === "KNOWN" ? "HARD" : "SOFT"} />
                  <span className={cn("chip rounded-sm px-1.5 py-0.5 text-[10px]", e.certainty === "KNOWN" ? "!text-[#9be9c2]" : "")}>
                    {e.certainty}
                  </span>
                </div>
                <p className="mt-1 text-sm text-[#dfe9f5]">{e.description}</p>
                <div className="mt-1 flex flex-wrap gap-1 text-[10px] tracking-[0.08em] text-[#46597a]">
                  {e.source_evidence_ids?.map((s) => (
                    <span key={s} className="rounded-sm border border-[#0d1c38] bg-[#060b16] px-1 py-0.5">
                      {s}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="space-y-6">
        <section className="enter enter-2">
          <SectionTitle>Forensic anchors</SectionTitle>
          {!anchors || anchors.length === 0 ? (
            <EmptyState message="No forensic anchors." />
          ) : (
            <div className="space-y-2">
              {anchors.map((a) => (
                <Card key={a.anchor_id} className="hud-scan p-3">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-[#ffb454]">{a.anchor_id}</span>
                    <span className="chip rounded-sm px-1.5 py-0.5">{a.type}</span>
                    <SeverityDot level={a.strength} />
                  </div>
                  <p className="mt-1.5 text-sm text-[#dfe9f5]">
                    {typeof a.value === "object" && a.value
                      ? Object.entries(a.value)
                          .map(([k, v]) => `${k}: ${v}`)
                          .join(" · ")
                      : a.normalized}
                  </p>
                  <div className="mt-1 text-[10px] uppercase tracking-[0.1em] text-[#46597a]">
                    Source: {a.source_evidence_ids.join(", ") || "—"}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>

        <section className="enter enter-3">
          <SectionTitle>Conflicts</SectionTitle>
          {!conflicts || conflicts.length === 0 ? (
            <EmptyState message="No evidence conflicts detected." />
          ) : (
            <div className="space-y-2">
              {conflicts.map((c) => (
                <Card key={c.conflict_id} className="hud-sweep border-[#3a1530]/60 p-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-[#ff5c5c]">{c.conflict_id}</span>
                    <StatusBadge status={c.status} />
                  </div>
                  <p className="mt-1.5 text-sm text-[#dfe9f5]">{c.subject}</p>
                  <p className="mt-1 text-xs text-[#7e93b3]">{c.description}</p>
                </Card>
              ))}
            </div>
          )}
        </section>

        <section className="enter enter-4">
          <SectionTitle>Constraints</SectionTitle>
          {!constraints || constraints.length === 0 ? (
            <EmptyState message="No constraints derived." />
          ) : (
            <div className="space-y-2">
              {constraints.map((c) => (
                <Card key={c.constraint_id} className="flex items-start gap-2 p-3">
                  <SeverityDot level={c.severity} />
                  <div className="min-w-0 flex-1">
                    <div className="text-[10px] uppercase tracking-[0.14em] text-[#7e93b3]">{c.type}</div>
                    <p className="mt-0.5 text-xs text-[#a9bcd9]">{c.description}</p>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
