"use client";

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
