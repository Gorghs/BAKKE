"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { Led, StatusBadge } from "@/components/ui";
import { cn } from "@/lib/utilities";
import { useCase } from "@/features/cases/hooks";

const TABS = [
  { path: "", label: "Overview", code: "01" },
  { path: "/evidence", label: "Evidence", code: "02" },
  { path: "/timeline", label: "Timeline", code: "03" },
  { path: "/scenarios", label: "Scenarios", code: "04" },
  { path: "/compare", label: "Compare", code: "05" },
  { path: "/visualization", label: "Visualization", code: "06" },
  { path: "/audit", label: "Audit", code: "07" },
];

export function CaseShell({ children }: { children: React.ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { data: cs, isError } = useCase(id);

  const statusColor =
    cs?.status === "ANALYZED" ? "#5ce0a0" : cs?.status === "DRAFT" ? "#4cc9f0" : "#ffb454";

  return (
    <div className="space-y-6">
      <section aria-label="Case file header" className="hud-panel hud-corners hud-sweep relative rounded-md p-4">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[10px] uppercase tracking-[0.3em] text-[#46597a]">Case file</span>
          <span className="font-mono text-xs text-[#4cc9f0]">#{id?.slice(0, 8)}</span>
          <Led color={statusColor} />
          <h1 className="text-xl font-black uppercase tracking-[0.08em] text-[#dfe9f5]">
            {cs ? cs.name : isError ? <span className="term-danger">Case file unavailable</span> : "Loading…"}
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

      <nav aria-label="Case sections" className="flex gap-0.5 overflow-x-auto border-b border-[#0d1c38] pb-0 text-xs">
        {TABS.map((t) => {
          const target = `/cases/${id}${t.path}`;
          const active = pathname === target;
          return (
            <Link
              key={t.path}
              href={target}
              aria-current={active ? "page" : undefined}
              className={cn(
                "group relative flex items-center gap-1.5 whitespace-nowrap px-3 py-2.5 font-bold uppercase tracking-[0.14em] transition",
                active ? "text-[#4cc9f0]" : "text-[#7e93b3] hover:text-[#dfe9f5]"
              )}
            >
              <span className="text-[9px] text-[#46597a]">{t.code}</span>
              {t.label}
              {active && (
                <span aria-hidden="true" className="absolute inset-x-1 -bottom-px h-0.5 bg-[#4cc9f0] shadow-[0_0_10px_#4cc9f0]" />
              )}
            </Link>
          );
        })}
      </nav>

      {children}
    </div>
  );
}
