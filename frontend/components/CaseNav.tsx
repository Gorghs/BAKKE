"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { cn } from "@/lib/api";

const TABS = [
  { path: "", label: "Overview", code: "01" },
  { path: "/evidence", label: "Evidence", code: "02" },
  { path: "/timeline", label: "Timeline", code: "03" },
  { path: "/scenarios", label: "Scenarios", code: "04" },
  { path: "/compare", label: "Compare", code: "05" },
  { path: "/visualization", label: "Visualization", code: "06" },
  { path: "/audit", label: "Audit", code: "07" },
];

/**
 * Section tabs for everything under /cases/{id}.
 *
 * Lives in its own component so the case layout stays small enough to read.
 * A tab is active on its own page and on any page below it, so a scenario
 * detail page keeps the Scenarios tab lit.
 */
export function CaseNav() {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();

  return (
    <nav className="flex gap-0.5 overflow-x-auto border-b border-[#0d1c38] pb-0 text-xs">
      {TABS.map((t) => {
        const target = `/cases/${id}${t.path}`;
        const active = t.path
          ? pathname === target || pathname.startsWith(`${target}/`)
          : pathname === target;
        return (
          <Link
            key={t.path}
            href={target}
            className={cn(
              "group relative flex items-center gap-1.5 whitespace-nowrap px-3 py-2.5 font-bold uppercase tracking-[0.14em] transition",
              active ? "text-[#4cc9f0]" : "text-[#7e93b3] hover:text-[#dfe9f5]",
            )}
          >
            <span className="text-[9px] text-[#46597a]">{t.code}</span>
            {t.label}
            {active && (
              <span className="absolute inset-x-1 -bottom-px h-0.5 bg-[#4cc9f0] shadow-[0_0_10px_#4cc9f0]" />
            )}
          </Link>
        );
      })}
    </nav>
  );
}
