"use client";

export function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score));
  const color = pct >= 75 ? "#5ce0a0" : pct >= 50 ? "#ffb454" : "#ff5c5c";
  return (
    <div
      className="flex items-center gap-2"
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Evidence consistency score"
    >
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
