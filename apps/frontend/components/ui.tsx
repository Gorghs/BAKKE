"use client";

import { cn } from "@/lib/api";

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
        className="led-static"
        style={{ background: m.dot, color: m.dot, animation: blink ? "led-pulse 1.2s ease-in-out infinite" : undefined }}
      />
      {status}
    </span>
  );
}

export function SeverityDot({ level }: { level: string }) {
  const color = level === "HARD" ? "#ff5c5c" : level === "SOFT" ? "#ffb454" : "#7e93b3";
  return (
    <span
      className="led"
      style={{ background: color, color, animationDuration: level === "HARD" ? "0.8s" : "1.6s" }}
      title={level}
    />
  );
}

export function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color = pct >= 75 ? "#5ce0a0" : pct >= 50 ? "#ffb454" : "#ff5c5c";
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-2 w-24 overflow-hidden rounded-sm border border-white/10 bg-black/50">
        <div
          className="striped h-full transition-all duration-700"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
        <div
          className="absolute inset-0"
          style={{ boxShadow: `0 0 8px ${color}66, inset 0 0 6px rgba(0,0,0,0.4)` }}
        />
      </div>
      <span className="text-xs font-bold tabular-nums" style={{ color }}>
        {score}
      </span>
    </div>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("hud-panel hud-corners rounded-md", className)}>{children}</div>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="hud-title mb-3">{children}</h2>;
}

export function Spinner() {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-xs uppercase tracking-[0.2em] text-[#7e93b3]">
      <div className="radar">
        <div className="blip" />
      </div>
      <span>scanning</span>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="hud-panel hud-corners relative rounded-md border-dashed py-10 text-center">
      <p className="px-4 text-xs uppercase tracking-[0.16em] text-[#7e93b3]">{message}</p>
      <p className="mt-2 text-[10px] tracking-[0.3em] text-[#46597a]">NO DATA</p>
    </div>
  );
}

export function Led({ color, pulse = true }: { color: string; pulse?: boolean }) {
  return (
    <span
      className={pulse ? "led" : "led-static"}
      style={{ background: color, color, boxShadow: `0 0 6px ${color}88` }}
    />
  );
}

export function Stat({ label, value, accent = "#dfe9f5" }: { label: string; value: string; accent?: string }) {
  return (
    <div className="hud-panel hud-corners relative rounded-md px-4 py-3">
      <div className="text-xl font-bold tabular-nums tracking-tight" style={{ color: accent }}>
        {value}
      </div>
      <div className="mt-0.5 text-[10px] uppercase tracking-[0.18em] text-[#7e93b3]">{label}</div>
    </div>
  );
}

export function HudTag({ children }: { children: React.ReactNode }) {
  return <span className="chip inline-block rounded-sm px-1.5 py-0.5 uppercase tracking-[0.12em]">{children}</span>;
}
