"use client";

import { cn } from "@/lib/utilities";

const STATUS_META: Record<string, { dot: string; cls: string }> = {
  DRAFT: { dot: "#46597a", cls: "text-[#8aa4c8]" },
  ANALYZING: { dot: "#ffb454", cls: "text-[#ffce8a] animated-blink" },
  ANALYZED: { dot: "#5ce0a0", cls: "text-[#9be9c2]" },
  ERROR: { dot: "#ff5c5c", cls: "text-[#ffb0b0]" },
  SURVIVING: { dot: "#5ce0a0", cls: "text-[#9be9c2]" },
  REJECTED: { dot: "#ff5c5c", cls: "text-[#ffb0b0]" },
  PENDING: { dot: "#7e93b3", cls: "text-[#a9bcd9]" },
  VALIDATING: { dot: "#4cc9f0", cls: "text-[#9adcf5]" },
  READY: { dot: "#5ce0a0", cls: "text-[#9be9c2]" },
  GENERATING: { dot: "#ffb454", cls: "text-[#ffce8a]" },
  FAILED: { dot: "#ff5c5c", cls: "text-[#ffb0b0]" },
  INVALID: { dot: "#ff5c5c", cls: "text-[#ffb0b0]" },
  PROCESSED: { dot: "#4cc9f0", cls: "text-[#9adcf5]" },
  UPLOADED: { dot: "#7e93b3", cls: "text-[#a9bcd9]" },
  SOFT: { dot: "#ffb454", cls: "text-[#ffce8a]" },
  HARD: { dot: "#ff5c5c", cls: "text-[#ffb0b0]" },
};

export function StatusBadge({ status }: { status: string }) {
  const m = STATUS_META[status] || { dot: "#7e93b3", cls: "text-[#a9bcd9]" };
  const blink = m.cls.includes("animated-blink");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em]",
        blink ? "animate-pulse" : "",
        "border-current/30",
        m.cls
      )}
      style={{ borderColor: `${m.dot}55` }}
    >
      <span
        aria-hidden="true"
        className="led-static"
        style={{ background: m.dot, color: m.dot, animation: blink ? "led-pulse 1.2s ease-in-out infinite" : undefined }}
      />
      {status}
    </span>
  );
}
