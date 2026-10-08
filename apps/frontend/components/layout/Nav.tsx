"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Led } from "@/components/ui";
import { useProviders } from "@/features/providers/hooks";
import { useInterval } from "@/hooks/useInterval";

const LINKS = [
  { href: "/", label: "Command" },
  { href: "/cases", label: "Case Board" },
];

function Clock() {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
  }, []);
  useInterval(() => setNow(new Date()), 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return (
    <span className="hidden font-mono text-xs tracking-[0.18em] text-[#7e93b3] md:inline">
      <time dateTime={now ? now.toISOString() : undefined}>
        {now ? `${p(now.getHours())}:${p(now.getMinutes())}:${p(now.getSeconds())}Z` : "--:--:--"}
      </time>
    </span>
  );
}

export default function Nav() {
  const pathname = usePathname();
  const { data: providers } = useProviders(15_000);

  const llm = providers?.llm;
  const mockAny = providers ? Object.values(providers).some((v) => (v as { is_mock?: boolean })?.is_mock) : false;

  return (
    <header className="sticky top-0 z-30 border-b border-[#14305c]/60 bg-[#04070f]/85 backdrop-blur-md">
      <div className="relative">
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-[#4cc9f0]/70 to-transparent" />
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-2.5 sm:px-6 lg:px-8">
          <Link href="/" className="flicker flex shrink-0 items-center gap-2.5">
            <span className="relative grid h-9 w-9 place-items-center">
              <svg viewBox="0 0 36 36" className="h-9 w-9" aria-hidden="true" focusable="false">
                <path
                  d="M18 2 L32 7 V17 C32 26 26 32 18 34 C10 32 4 26 4 17 V7 Z"
                  fill="none"
                  stroke="#4cc9f0"
                  strokeWidth="1.6"
                />
                <path
                  d="M18 2 L32 7 V17 C32 26 26 32 18 34 C10 32 4 26 4 17 V7 Z"
                  fill="#0b1428"
                />
                <text
                  x="18"
                  y="22"
                  textAnchor="middle"
                  fill="#4cc9f0"
                  fontSize="15"
                  fontFamily="ui-monospace, monospace"
                  fontWeight="bold"
                >
                  B
                </text>
              </svg>
              <span aria-hidden="true" className="led absolute -right-0.5 -top-0.5" style={{ color: "#5ce0a0" }} />
            </span>
            <span className="hidden sm:block">
              <span className="block text-sm font-black uppercase tracking-[0.28em] text-[#dfe9f5]">
                Bakke<span className="text-[#4cc9f0]"> Command</span>
              </span>
              <span className="block text-[9px] uppercase tracking-[0.34em] text-[#46597a]">
                Evidence-Constrained Intelligence
              </span>
            </span>
          </Link>

          <nav aria-label="Primary" className="flex items-center gap-1 text-xs">
            {LINKS.map((l) => {
              const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
              return (
                <Link
                  key={l.href}
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={`relative rounded-sm px-3 py-1.5 font-bold uppercase tracking-[0.16em] transition ${
                    active ? "text-[#4cc9f0]" : "text-[#7e93b3] hover:text-[#dfe9f5]"
                  }`}
                >
                  {active && (
                    <span aria-hidden="true" className="absolute inset-x-1 -bottom-px h-px bg-[#4cc9f0] shadow-[0_0_8px_#4cc9f0]" />
                  )}
                  {l.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-4 text-[10px] uppercase tracking-[0.16em] text-[#7e93b3]">
            <span className="hidden items-center gap-1.5 sm:flex">
              <Led color={mockAny ? "#ffb454" : "#5ce0a0"} pulse={mockAny} />
              {mockAny ? "Dev Mock Mode" : "Live Providers"}
            </span>
            <span className="hidden items-center gap-1.5 lg:flex">
              <Led color={llm?.is_mock ? "#ffb454" : "#5ce0a0"} pulse={llm?.is_mock} />
              LLM:{llm?.is_mock ? "mock" : (llm?.provider || "?")}
            </span>
            <span className="hidden items-center gap-1.5 lg:flex">
              <Led color="#5ce0a0" />
              SYS:ON
            </span>
            <Clock />
            <span className="chip hidden rounded-sm px-1.5 py-0.5 text-[9px] sm:inline">STN-07</span>
          </div>
        </div>
      </div>
    </header>
  );
}
